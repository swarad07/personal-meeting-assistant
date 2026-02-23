from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_mcp_registry, get_scheduler
from app.db.postgres import get_db_session
from app.mcp.base import ProviderStatus
from app.mcp.registry import MCPRegistry
from app.models.briefing import Briefing
from app.services.scheduler import SchedulerService

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
