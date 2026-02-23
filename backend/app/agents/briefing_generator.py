"""BriefingGeneratorAgent: Generates pre-meeting briefings using GPT-4o.

Standalone runner generate_briefings_for_upcoming() works with meetings from the DB
(previously synced from Granola, which includes calendar data) and generates briefings
with attendee context, previous meeting history, and open action items.

Requires an OpenAI API key.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentState, BaseAgent
from app.config import settings
from app.models.action_item import ActionItem
from app.models.briefing import Briefing
from app.models.meeting import Attendee, Meeting
from app.models.profile import Profile

logger = logging.getLogger(__name__)

BRIEFING_SYSTEM_PROMPT = """You are a professional meeting preparation assistant. Given context about
an upcoming meeting—its attendees, their profiles, previous interactions, open action items,
and related topics—produce a clear, actionable pre-meeting briefing.

Your briefing should include:

1. **Meeting Overview**: A brief summary of what this meeting is likely about.
2. **Attendee Context**: For each known attendee, summarize who they are, your past interactions, and anything notable.
3. **Open Action Items**: List any unresolved todos or action items relevant to the attendees or topics.
4. **Suggested Discussion Points**: 3-5 recommended topics to discuss, based on pending items and past context.
5. **Key Reminders**: Anything important the user should keep in mind.

Output valid JSON with keys: overview, attendees, action_items, discussion_points, reminders.
Each value should be a string or list of strings. Keep it concise and professional."""


NEXT_CALL_SYSTEM_PROMPT = """You are a meeting preparation assistant. You have just reviewed a completed meeting
— its transcript, notes, summary, action items, and attendees. Your task is to produce a concise "Next Call Brief"
that tells the user exactly what they need to be ready with for their next interaction with these people.

Your brief should include:

1. **Follow-ups Required**: Action items, promises made, or commitments that need to be fulfilled before the next call.
2. **Open Questions**: Anything left unresolved or unclear that should be revisited.
3. **Key Decisions Made**: Important decisions from this meeting the user should remember.
4. **Preparation Checklist**: Concrete things the user should do or prepare before the next meeting.
5. **Relationship Notes**: Anything notable about attendee dynamics, preferences, or concerns to keep in mind.

Be specific and actionable. Reference actual content from the meeting. Keep it concise.
Output as markdown text (not JSON)."""


async def generate_next_call_brief(meeting_id: str) -> dict[str, Any]:
    """Generate a 'next call brief' for a specific completed meeting."""
    from app.db.postgres import async_session_factory

    if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
        raise RuntimeError("No OpenAI API key configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with async_session_factory() as session:
        from app.models.meeting import TranscriptChunk

        stmt = select(Meeting).where(Meeting.id == meeting_id)
        result = await session.execute(stmt)
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        att_stmt = select(Attendee.name, Attendee.email).where(Attendee.meeting_id == meeting.id)
        attendees = (await session.execute(att_stmt)).all()

        transcript_stmt = (
            select(TranscriptChunk.speaker, TranscriptChunk.content)
            .where(TranscriptChunk.meeting_id == meeting.id)
            .order_by(TranscriptChunk.chunk_index)
        )
        chunks = (await session.execute(transcript_stmt)).all()

        ai_stmt = select(ActionItem).where(ActionItem.meeting_id == meeting.id)
        action_items = (await session.execute(ai_stmt)).scalars().all()

        context = await _gather_meeting_context(session, meeting.id, meeting.title)

    prompt_parts = [
        f"## Meeting: {meeting.title}",
        f"- Date: {meeting.date.isoformat() if meeting.date else 'N/A'}",
    ]

    if meeting.summary:
        prompt_parts.append(f"\n### Summary\n{meeting.summary}")

    notes = meeting.enhanced_notes or meeting.raw_notes
    if notes:
        trimmed = notes[:3000] if len(notes) > 3000 else notes
        prompt_parts.append(f"\n### Notes\n{trimmed}")

    if attendees:
        prompt_parts.append("\n### Attendees")
        for a in attendees:
            prompt_parts.append(f"- {a.name}" + (f" ({a.email})" if a.email else ""))

    if chunks:
        prompt_parts.append("\n### Transcript (key segments)")
        transcript_text = "\n".join(
            f"{c.speaker or 'Unknown'}: {c.content}" for c in chunks[:40]
        )
        if len(transcript_text) > 4000:
            transcript_text = transcript_text[:4000] + "\n... (truncated)"
        prompt_parts.append(transcript_text)

    if action_items:
        prompt_parts.append("\n### Action Items from This Meeting")
        for ai in action_items:
            status_tag = f"[{ai.status}]"
            assignee = f" ({ai.assignee})" if ai.assignee else ""
            prompt_parts.append(f"- {status_tag}{assignee} {ai.description}")

    if context.get("previous_meetings"):
        prompt_parts.append("\n### Previous Meetings with Same Attendees")
        for pm in context["previous_meetings"]:
            prompt_parts.append(f"- {pm['title']} ({pm['date']}): {pm['summary']}")

    if context.get("action_items"):
        prompt_parts.append("\n### Other Open Action Items with These People")
        for ai in context["action_items"]:
            prompt_parts.append(f"- [{ai['assignee']}] {ai['description']}")

    prompt = "\n".join(prompt_parts)

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": NEXT_CALL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    brief_content = resp.choices[0].message.content or "No brief generated."

    async with async_session_factory() as save_session:
        save_stmt = select(Meeting).where(Meeting.id == meeting_id)
        save_result = await save_session.execute(save_stmt)
        m = save_result.scalar_one_or_none()
        if m:
            m.next_call_brief = brief_content
            await save_session.commit()

    return {
        "status": "success",
        "meeting_id": meeting_id,
        "meeting_title": meeting.title,
        "brief": brief_content,
    }


async def generate_briefings_for_upcoming(hours_ahead: int = 48) -> dict[str, Any]:
    """Standalone briefing generator — works from DB meetings."""
    from app.db.postgres import async_session_factory

    if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
        return {"generated": 0, "skipped_reason": "No OpenAI API key configured"}

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    generated = 0
    errors: list[dict[str, Any]] = []

    now = datetime.utcnow()
    cutoff = now + timedelta(hours=hours_ahead)

    async with async_session_factory() as session:
        upcoming_stmt = (
            select(Meeting.id, Meeting.title, Meeting.date)
            .where(Meeting.date >= now, Meeting.date <= cutoff)
            .order_by(Meeting.date)
        )
        result = await session.execute(upcoming_stmt)
        upcoming = result.all()

        if not upcoming:
            upcoming_stmt = (
                select(Meeting.id, Meeting.title, Meeting.date)
                .order_by(Meeting.date.desc())
                .limit(5)
            )
            result = await session.execute(upcoming_stmt)
            upcoming = result.all()

        logger.info("Generating briefings for %d meetings", len(upcoming))

        for meeting_id, title, date in upcoming:
            try:
                existing = await session.execute(
                    select(Briefing).where(Briefing.meeting_id == meeting_id)
                )
                if existing.scalar_one_or_none():
                    continue

                context = await _gather_meeting_context(session, meeting_id, title)
                prompt = _build_briefing_prompt(title, date, context)

                resp = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                )

                raw = resp.choices[0].message.content or "{}"
                try:
                    structured = json.loads(raw)
                except json.JSONDecodeError:
                    structured = {"overview": raw}

                briefing = Briefing(
                    id=uuid.uuid4(),
                    meeting_id=meeting_id,
                    title=title or "Untitled Meeting",
                    content=_format_briefing_text(structured),
                    topics=structured.get("discussion_points"),
                    attendee_context=structured.get("attendees"),
                    action_items_context=structured.get("action_items"),
                )
                session.add(briefing)
                await session.flush()
                generated += 1
                logger.info("Generated briefing for '%s'", title)

            except Exception as e:
                logger.warning("Briefing generation failed for %s: %s", title, e)
                errors.append({"meeting_id": str(meeting_id), "title": title, "error": str(e)})

        await session.commit()

    return {"generated": generated, "errors": errors}


async def _gather_meeting_context(
    session: AsyncSession, meeting_id: uuid.UUID, title: str
) -> dict[str, Any]:
    """Gather context from DB for the briefing prompt."""
    att_stmt = select(Attendee.name, Attendee.email).where(Attendee.meeting_id == meeting_id)
    att_result = await session.execute(att_stmt)
    attendees = att_result.all()

    attendee_emails = [a.email for a in attendees if a.email]
    attendee_names = [a.name for a in attendees]

    profiles = []
    for email in attendee_emails:
        stmt = select(Profile).where(func.lower(Profile.email) == email.lower())
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        if profile:
            profiles.append({
                "name": profile.name,
                "email": profile.email,
                "bio": profile.bio,
                "traits": profile.traits,
            })

    prev_meetings: list[dict] = []
    if attendee_emails:
        subq = (
            select(Attendee.meeting_id)
            .where(Attendee.email.in_(attendee_emails))
            .where(Attendee.meeting_id != meeting_id)
            .distinct()
            .subquery()
        )
        stmt = (
            select(Meeting.title, Meeting.date, Meeting.summary)
            .where(Meeting.id.in_(select(subq.c.meeting_id)))
            .order_by(Meeting.date.desc())
            .limit(5)
        )
        result = await session.execute(stmt)
        for m_title, m_date, m_summary in result.all():
            prev_meetings.append({
                "title": m_title,
                "date": m_date.isoformat() if m_date else "",
                "summary": m_summary or "(no summary)",
            })

    action_items: list[dict] = []
    if attendee_names:
        stmt = (
            select(ActionItem)
            .where(ActionItem.status == "open", ActionItem.assignee.in_(attendee_names))
            .limit(10)
        )
        result = await session.execute(stmt)
        for ai in result.scalars().all():
            action_items.append({
                "assignee": ai.assignee,
                "description": ai.description,
                "due_date": ai.due_date.isoformat() if ai.due_date else None,
            })

    return {
        "attendees": [{"name": a.name, "email": a.email} for a in attendees],
        "profiles": profiles,
        "previous_meetings": prev_meetings,
        "action_items": action_items,
    }


def _build_briefing_prompt(
    title: str, date: datetime | None, context: dict[str, Any]
) -> str:
    parts = [
        f"## Upcoming Meeting: {title}",
        f"- **Date**: {date.isoformat() if date else 'N/A'}",
    ]

    parts.append("\n### Attendees")
    for att in context["attendees"]:
        line = f"- {att['name']}"
        if att.get("email"):
            line += f" ({att['email']})"
        parts.append(line)

    if context["profiles"]:
        parts.append("\n### Known Attendee Profiles")
        for p in context["profiles"]:
            parts.append(f"- **{p['name']}** ({p.get('email', '')})")
            if p.get("bio"):
                parts.append(f"  Bio: {p['bio']}")
            traits = p.get("traits") or {}
            if traits.get("meeting_count"):
                parts.append(f"  Meetings together: {traits['meeting_count']}")

    if context["previous_meetings"]:
        parts.append("\n### Previous Meetings with These Attendees")
        for pm in context["previous_meetings"]:
            parts.append(f"- **{pm['title']}** ({pm['date']}): {pm['summary']}")

    if context["action_items"]:
        parts.append("\n### Open Action Items")
        for ai in context["action_items"]:
            due = f" (due: {ai['due_date']})" if ai.get("due_date") else ""
            parts.append(f"- [{ai['assignee']}] {ai['description']}{due}")

    return "\n".join(parts)


def _format_briefing_text(structured: dict[str, Any]) -> str:
    sections = []

    if structured.get("overview"):
        sections.append(f"## Overview\n{structured['overview']}")

    if structured.get("attendees"):
        att = structured["attendees"]
        if isinstance(att, list):
            sections.append("## Attendees\n" + "\n".join(f"- {a}" for a in att))
        elif isinstance(att, str):
            sections.append(f"## Attendees\n{att}")

    if structured.get("discussion_points"):
        dp = structured["discussion_points"]
        if isinstance(dp, list):
            sections.append("## Discussion Points\n" + "\n".join(f"- {p}" for p in dp))
        elif isinstance(dp, str):
            sections.append(f"## Discussion Points\n{dp}")

    if structured.get("action_items"):
        ai = structured["action_items"]
        if isinstance(ai, list):
            sections.append("## Open Action Items\n" + "\n".join(f"- {a}" for a in ai))
        elif isinstance(ai, str):
            sections.append(f"## Open Action Items\n{ai}")

    if structured.get("reminders"):
        rem = structured["reminders"]
        if isinstance(rem, list):
            sections.append("## Key Reminders\n" + "\n".join(f"- {r}" for r in rem))
        elif isinstance(rem, str):
            sections.append(f"## Key Reminders\n{rem}")

    return "\n\n".join(sections) if sections else "No briefing content generated."


class BriefingGeneratorAgent(BaseAgent):
    name = "briefing_generator"
    description = "Generates pre-meeting briefings for upcoming calendar events"
    pipeline = "briefing"
    dependencies = ["calendar_agent"]
    required_mcp_providers = []

    async def should_run(self, state: AgentState) -> bool:
        if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
            logger.warning("No OpenAI API key, skipping briefing generation")
            return False
        upcoming = state.get("upcoming_meetings", [])
        return len(upcoming) > 0

    async def process(self, state: AgentState) -> AgentState:
        result = await generate_briefings_for_upcoming()
        errors = list(state.get("errors", []))
        for e in result.get("errors", []):
            errors.append({"agent": self.name, **e})
        return {
            **state,
            "briefing": {"generated": result.get("generated", 0)},
            "errors": errors,
        }
