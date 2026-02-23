from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_mcp_registry, get_scheduler
from app.config import settings
from app.db.postgres import get_db_session
from app.mcp.base import ProviderStatus
from app.mcp.registry import MCPRegistry
from app.models.action_item import ActionItem
from app.models.briefing import Briefing
from app.models.meeting import Attendee, Meeting
from app.models.profile import Profile
from app.services.scheduler import SchedulerService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/events")
async def list_events(
    days: int = 7,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
):
    try:
        gcal = mcp_registry.get("gcal")
    except KeyError:
        raise HTTPException(status_code=503, detail="Google Calendar MCP not configured")

    status = await gcal.health_check()
    if status != ProviderStatus.HEALTHY:
        raise HTTPException(status_code=503, detail="Google Calendar MCP not connected")

    from datetime import datetime, timedelta

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days)).isoformat() + "Z"

    try:
        raw = await gcal.execute_tool("list-events", {
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": 50,
        })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch events: {e}")

    events = _parse_events(raw)
    return {"events": events, "count": len(events)}


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        gcal = mcp_registry.get("gcal")
    except KeyError:
        raise HTTPException(status_code=503, detail="Google Calendar MCP not configured")

    try:
        raw = await gcal.execute_tool("get-event", {"eventId": event_id})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch event: {e}")

    if not raw:
        raise HTTPException(status_code=404, detail="Event not found")

    event = _normalize_event(raw if isinstance(raw, dict) else {})

    stmt = select(Briefing).where(Briefing.calendar_event_id == event_id)
    result = await session.execute(stmt)
    briefing = result.scalar_one_or_none()
    if briefing:
        event["briefing"] = {
            "id": str(briefing.id),
            "content": briefing.content,
            "topics": briefing.topics,
        }

    return event


@router.post("/sync", status_code=202)
async def trigger_calendar_sync(
    scheduler: SchedulerService = Depends(get_scheduler),
):
    result = await scheduler.trigger_pipeline("briefing", trigger="manual")
    return {"message": "Briefing pipeline triggered", "result": result}


@router.post("/events/{event_id}/generate-briefing")
async def generate_event_briefing(
    event_id: str,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session: AsyncSession = Depends(get_db_session),
):
    """Generate an AI briefing for an upcoming calendar event by finding
    similar past meetings (by title keywords + attendee overlap)."""

    if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")

    try:
        gcal = mcp_registry.get("gcal")
    except KeyError:
        raise HTTPException(status_code=503, detail="Google Calendar not configured")

    try:
        raw = await gcal.execute_tool("get-event", {"eventId": event_id})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch event: {e}")

    if not raw:
        raise HTTPException(status_code=404, detail="Event not found")

    event = _normalize_event(raw if isinstance(raw, dict) else {})
    title = event.get("title", "Untitled")
    attendees = event.get("attendees", [])
    attendee_emails = [a["email"] for a in attendees if a.get("email")]

    similar = await _find_similar_meetings(session, title, attendee_emails)
    profiles = await _gather_attendee_profiles(session, attendee_emails)
    action_items = await _gather_open_action_items(session, attendees)

    from app.agents.briefing_generator import (
        BRIEFING_SYSTEM_PROMPT,
        _format_briefing_text,
    )

    prompt = _build_event_briefing_prompt(event, similar, profiles, action_items)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw_text = resp.choices[0].message.content or "{}"
    try:
        structured = json.loads(raw_text)
    except json.JSONDecodeError:
        structured = {"overview": raw_text}

    existing_stmt = select(Briefing).where(Briefing.calendar_event_id == event_id)
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()

    if existing:
        existing.content = _format_briefing_text(structured)
        existing.topics = structured.get("discussion_points")
        existing.attendee_context = structured.get("attendees")
        existing.action_items_context = structured.get("action_items")
    else:
        briefing = Briefing(
            id=uuid.uuid4(),
            calendar_event_id=event_id,
            title=title,
            content=_format_briefing_text(structured),
            topics=structured.get("discussion_points"),
            attendee_context=structured.get("attendees"),
            action_items_context=structured.get("action_items"),
        )
        session.add(briefing)

    await session.commit()

    final_stmt = select(Briefing).where(Briefing.calendar_event_id == event_id)
    final_briefing = (await session.execute(final_stmt)).scalar_one()

    return {
        "status": "success",
        "briefing": {
            "id": str(final_briefing.id),
            "content": final_briefing.content,
            "topics": final_briefing.topics,
        },
        "similar_meetings": [
            {"id": str(m["id"]), "title": m["title"], "date": m["date"]}
            for m in similar
        ],
    }


async def _find_similar_meetings(
    session: AsyncSession,
    title: str,
    attendee_emails: list[str],
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Find past meetings that are similar by title keywords or shared attendees."""
    STOP_WORDS = {
        "the", "and", "for", "with", "meeting", "call", "sync", "weekly",
        "daily", "standup", "stand", "check", "update", "review", "team",
    }
    keywords = [w for w in title.lower().split() if len(w) > 2 and w not in STOP_WORDS]

    title_meeting_ids: set[uuid.UUID] = set()
    if keywords:
        conditions = [Meeting.title.ilike(f"%{kw}%") for kw in keywords[:5]]
        stmt = (
            select(Meeting.id)
            .where(or_(*conditions))
            .order_by(Meeting.date.desc())
            .limit(limit * 2)
        )
        result = await session.execute(stmt)
        title_meeting_ids = {row[0] for row in result.all()}

    attendee_meeting_ids: set[uuid.UUID] = set()
    if attendee_emails:
        stmt = (
            select(Attendee.meeting_id)
            .where(Attendee.email.in_(attendee_emails))
            .distinct()
        )
        result = await session.execute(stmt)
        attendee_meeting_ids = {row[0] for row in result.all()}

    both = title_meeting_ids & attendee_meeting_ids
    title_only = title_meeting_ids - both
    attendee_only = attendee_meeting_ids - both

    ranked_ids = list(both) + list(title_only) + list(attendee_only)
    ranked_ids = ranked_ids[:limit]

    if not ranked_ids:
        return []

    stmt = (
        select(Meeting.id, Meeting.title, Meeting.date, Meeting.summary)
        .where(Meeting.id.in_(ranked_ids))
        .order_by(Meeting.date.desc())
    )
    result = await session.execute(stmt)
    return [
        {
            "id": row.id,
            "title": row.title,
            "date": row.date.isoformat() if row.date else "",
            "summary": row.summary or "(no summary)",
        }
        for row in result.all()
    ]


async def _gather_attendee_profiles(
    session: AsyncSession, emails: list[str]
) -> list[dict[str, Any]]:
    profiles = []
    for email in emails:
        stmt = select(Profile).where(func.lower(Profile.email) == email.lower())
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            profiles.append({
                "name": profile.name,
                "email": profile.email,
                "bio": profile.bio,
                "traits": profile.traits,
            })
    return profiles


async def _gather_open_action_items(
    session: AsyncSession, attendees: list[dict]
) -> list[dict[str, Any]]:
    names = [a.get("name") or a.get("email", "").split("@")[0] for a in attendees if a.get("name") or a.get("email")]
    if not names:
        return []
    stmt = (
        select(ActionItem)
        .where(ActionItem.status == "open", ActionItem.assignee.in_(names))
        .limit(15)
    )
    result = await session.execute(stmt)
    return [
        {
            "assignee": ai.assignee,
            "description": ai.description,
            "due_date": ai.due_date.isoformat() if ai.due_date else None,
        }
        for ai in result.scalars().all()
    ]


def _build_event_briefing_prompt(
    event: dict,
    similar_meetings: list[dict],
    profiles: list[dict],
    action_items: list[dict],
) -> str:
    parts = [
        f"## Upcoming Meeting: {event.get('title', 'Untitled')}",
        f"- **Start**: {event.get('start', 'N/A')}",
        f"- **End**: {event.get('end', 'N/A')}",
    ]
    if event.get("location"):
        parts.append(f"- **Location**: {event['location']}")
    if event.get("description"):
        desc = event["description"][:500]
        parts.append(f"- **Description**: {desc}")

    attendees = event.get("attendees", [])
    if attendees:
        parts.append("\n### Attendees")
        for att in attendees:
            name = att.get("name") or att.get("email") or "Unknown"
            email = att.get("email", "")
            parts.append(f"- {name}" + (f" ({email})" if email and email != name else ""))

    if profiles:
        parts.append("\n### Known Attendee Profiles")
        for p in profiles:
            parts.append(f"- **{p['name']}** ({p.get('email', '')})")
            if p.get("bio"):
                bio = p["bio"][:300]
                parts.append(f"  Bio: {bio}")
            traits = p.get("traits") or {}
            if traits.get("meeting_count"):
                parts.append(f"  Meetings together: {traits['meeting_count']}")

    if similar_meetings:
        parts.append("\n### Similar/Related Past Meetings")
        for m in similar_meetings:
            summary = m["summary"][:200] if len(m["summary"]) > 200 else m["summary"]
            parts.append(f"- **{m['title']}** ({m['date']}): {summary}")

    if action_items:
        parts.append("\n### Open Action Items with These People")
        for ai in action_items:
            due = f" (due: {ai['due_date']})" if ai.get("due_date") else ""
            parts.append(f"- [{ai['assignee']}] {ai['description']}{due}")

    return "\n".join(parts)


def _parse_events(raw):
    if isinstance(raw, list):
        return [_normalize_event(e) for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        items = raw.get("items", raw.get("events", []))
        return [_normalize_event(e) for e in items if isinstance(e, dict)]
    return []


def _normalize_event(event: dict) -> dict:
    attendees = []
    for att in event.get("attendees", []):
        if isinstance(att, str):
            attendees.append({"email": att})
        elif isinstance(att, dict):
            attendees.append({
                "email": att.get("email"),
                "name": att.get("displayName", att.get("name")),
                "response_status": att.get("responseStatus"),
            })

    start = event.get("start", {})
    end = event.get("end", {})

    return {
        "event_id": event.get("id"),
        "title": event.get("summary", event.get("title", "Untitled")),
        "start": start.get("dateTime", start) if isinstance(start, dict) else start,
        "end": end.get("dateTime", end) if isinstance(end, dict) else end,
        "description": event.get("description"),
        "location": event.get("location"),
        "attendees": attendees,
        "html_link": event.get("htmlLink"),
    }
