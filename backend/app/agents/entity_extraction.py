"""EntityExtractionAgent: Extracts entities and action items from meetings using GPT-4o.

Standalone runner extract_entities_for_meetings() processes meetings one by one
with individual DB sessions to avoid lazy-load / greenlet issues.

Requires an OpenAI API key. If unavailable, the agent skips gracefully.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.base import AgentState, BaseAgent
from app.config import settings
from app.models.action_item import ActionItem
from app.models.meeting import Meeting
from app.models.profile import Profile

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an entity extraction and summarization system. Given meeting notes and transcript, extract structured entities and generate a concise summary.

Return a JSON object with exactly these keys:
{
  "summary": "A concise 2-4 sentence summary of the meeting covering the main discussion points, decisions made, and outcomes.",
  "people": [
    {"name": "Full Name", "email": null, "role": null, "organization": null}
  ],
  "organizations": [
    {"name": "Org Name", "domain": null}
  ],
  "topics": [
    {"name": "Topic Name", "category": null}
  ],
  "projects": [
    {"name": "Project Name", "status": null}
  ],
  "action_items": [
    {"assignee": "Person Name", "description": "What needs to be done", "due_date": null}
  ]
}

Rules:
- The summary should capture what the meeting was about, key decisions, and next steps
- Extract ALL mentioned people, even those only referenced by name
- Normalize names to proper case (e.g., "sarah" -> "Sarah")
- For action items, always include an assignee if one is mentioned
- Due dates should be ISO format if parseable, otherwise null
- Be thorough but avoid hallucinating entities not present in the text
- Return valid JSON only, no markdown or explanation"""


async def extract_entities_for_meetings(
    meeting_ids: list[str] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Standalone entity extraction that works outside LangGraph."""
    from app.db.neo4j_driver import get_neo4j_driver
    from app.db.postgres import async_session_factory
    from app.services.neo4j_service import Neo4jService

    if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
        return {"processed": 0, "skipped_reason": "No OpenAI API key configured"}

    driver = await get_neo4j_driver()
    neo4j_svc = Neo4jService(driver)
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    processed = 0
    entities_count = 0
    action_items_count = 0
    errors: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        if meeting_ids:
            stmt = (
                select(Meeting)
                .options(
                    selectinload(Meeting.attendees),
                    selectinload(Meeting.transcript_chunks),
                )
                .where(Meeting.id.in_(meeting_ids))
            )
        else:
            from app.models.processing_status import MeetingProcessingStatus
            processed_ids_stmt = (
                select(MeetingProcessingStatus.meeting_id)
                .where(
                    MeetingProcessingStatus.agent_name == "entity_extraction",
                    MeetingProcessingStatus.status == "completed",
                )
            )
            try:
                processed_result = await session.execute(processed_ids_stmt)
                done_ids = {row[0] for row in processed_result.all()}
            except Exception:
                done_ids = set()

            stmt = (
                select(Meeting)
                .options(
                    selectinload(Meeting.attendees),
                    selectinload(Meeting.transcript_chunks),
                )
                .order_by(Meeting.date.desc())
                .limit(limit)
            )

        result = await session.execute(stmt)
        meetings = result.scalars().all()

    logger.info("Entity extraction: processing %d meetings", len(meetings))

    for meeting in meetings:
        try:
            text_content = _build_extraction_text(meeting)
            if not text_content.strip():
                continue

            extraction = await _call_llm(client, text_content)
            if not extraction:
                continue

            async with async_session_factory() as session:
                if extraction.get("summary"):
                    meeting_stmt = select(Meeting).where(Meeting.id == meeting.id)
                    meeting_result = await session.execute(meeting_stmt)
                    m = meeting_result.scalar_one_or_none()
                    if m and not m.summary:
                        m.summary = extraction["summary"]

                await neo4j_svc.create_meeting_node(
                    meeting_id=str(meeting.id),
                    title=meeting.title,
                    date=meeting.date.isoformat() if meeting.date else "",
                )

                for person in extraction.get("people", []):
                    person_id = (person.get("email") or
                                 person.get("name", "").lower().replace(" ", "_"))
                    if person_id:
                        await neo4j_svc.create_entity("Person", person_id, {
                            "name": person.get("name"),
                            "email": person.get("email"),
                        })
                        await neo4j_svc.create_relationship(
                            "Person", person_id,
                            "Meeting", str(meeting.id),
                            "MENTIONED_IN", {"count": 1},
                        )
                        if person.get("organization"):
                            org_id = person["organization"].lower().replace(" ", "_")
                            await neo4j_svc.create_entity("Organization", org_id, {
                                "name": person["organization"],
                            })
                            await neo4j_svc.create_relationship(
                                "Person", person_id,
                                "Organization", org_id,
                                "WORKS_AT", {"role": person.get("role")},
                            )

                        await _enrich_profile_traits(
                            session, person.get("name"),
                            role=person.get("role"),
                            organization=person.get("organization"),
                        )
                    entities_count += 1

                for org in extraction.get("organizations", []):
                    org_id = org.get("name", "").lower().replace(" ", "_")
                    if org_id:
                        await neo4j_svc.create_entity("Organization", org_id, {
                            "name": org["name"],
                            "domain": org.get("domain"),
                        })
                        await neo4j_svc.create_relationship(
                            "Organization", org_id,
                            "Meeting", str(meeting.id),
                            "MENTIONED_IN", {"count": 1},
                        )
                    entities_count += 1

                for topic in extraction.get("topics", []):
                    topic_id = topic.get("name", "").lower().replace(" ", "_")
                    if topic_id:
                        await neo4j_svc.create_entity("Topic", topic_id, {
                            "name": topic["name"],
                            "category": topic.get("category"),
                        })
                        await neo4j_svc.create_relationship(
                            "Meeting", str(meeting.id),
                            "Topic", topic_id,
                            "DISCUSSED", {"relevance_score": 1.0},
                        )
                    entities_count += 1

                for ai_data in extraction.get("action_items", []):
                    action_item = ActionItem(
                        meeting_id=meeting.id,
                        assignee=ai_data.get("assignee", "Unassigned"),
                        description=ai_data.get("description", ""),
                        status="open",
                        due_date=_parse_date(ai_data.get("due_date")),
                    )
                    session.add(action_item)
                    action_items_count += 1

                await session.commit()

            processed += 1

        except Exception as e:
            logger.warning("Entity extraction failed for meeting %s: %s", meeting.id, e)
            errors.append({"meeting_id": str(meeting.id), "error": str(e)})

    logger.info(
        "Entity extraction complete: %d processed, %d entities, %d action items, %d errors",
        processed, entities_count, action_items_count, len(errors),
    )
    return {
        "processed": processed,
        "entities": entities_count,
        "action_items": action_items_count,
        "errors": errors,
    }


async def _enrich_profile_traits(
    session: AsyncSession,
    name: str | None,
    role: str | None = None,
    organization: str | None = None,
) -> None:
    """Push observed role/organization into the matching Profile's traits."""
    if not name:
        return

    stmt = select(Profile).where(func.lower(Profile.name) == name.lower())
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        return

    traits = profile.traits or {}
    changed = False

    if role:
        observed_roles = set(traits.get("observed_roles", []))
        if role not in observed_roles:
            observed_roles.add(role)
            traits["observed_roles"] = sorted(observed_roles)
            changed = True

    if organization:
        observed_orgs = set(traits.get("organizations", []))
        if organization not in observed_orgs:
            observed_orgs.add(organization)
            traits["organizations"] = sorted(observed_orgs)
            changed = True

    if changed:
        profile.traits = traits


def _build_extraction_text(meeting: Meeting) -> str:
    parts = []
    if meeting.title:
        parts.append(f"Meeting: {meeting.title}")
    if meeting.summary:
        parts.append(f"Summary: {meeting.summary}")
    if meeting.raw_notes:
        notes = meeting.raw_notes[:3000]
        parts.append(f"Notes:\n{notes}")
    if meeting.enhanced_notes:
        parts.append(f"Enhanced Notes:\n{meeting.enhanced_notes[:2000]}")

    try:
        attendees = meeting.attendees
        if attendees:
            att_strs = [f"- {a.name} ({a.email or 'no email'})" for a in attendees]
            parts.append("Attendees:\n" + "\n".join(att_strs))
    except Exception:
        pass

    try:
        chunks = meeting.transcript_chunks
        if chunks:
            transcript_parts = []
            for chunk in sorted(chunks, key=lambda c: c.chunk_index)[:50]:
                if chunk.speaker:
                    transcript_parts.append(f"[{chunk.speaker}]: {chunk.content}")
                else:
                    transcript_parts.append(chunk.content)
            transcript_text = "\n".join(transcript_parts)[:4000]
            parts.append(f"Transcript:\n{transcript_text}")
    except Exception:
        pass

    return "\n\n".join(parts)


async def _call_llm(client: AsyncOpenAI, text: str) -> dict[str, Any] | None:
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": text[:8000]},
            ],
            temperature=0.1,
            max_completion_tokens=2000,
        )
        content = resp.choices[0].message.content
        if content:
            return json.loads(content)
    except Exception:
        logger.exception("LLM extraction call failed")
    return None


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


SUMMARY_SYSTEM_PROMPT = """You are a meeting summarizer. Given meeting notes and/or transcript, produce a concise 2-5 sentence summary.
Cover: what the meeting was about, key discussion points, decisions made, and next steps if any.
Return ONLY the summary text, no JSON, no markdown formatting."""


async def generate_summary_for_meeting(meeting_id: str) -> dict[str, Any]:
    """Generate or regenerate a summary for a single meeting using GPT-4o."""
    from app.db.postgres import async_session_factory

    if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
        raise RuntimeError("OpenAI API key not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with async_session_factory() as session:
        stmt = (
            select(Meeting)
            .options(
                selectinload(Meeting.attendees),
                selectinload(Meeting.transcript_chunks),
            )
            .where(Meeting.id == meeting_id)
        )
        result = await session.execute(stmt)
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        text = _build_extraction_text(meeting)
        if not text.strip():
            return {"status": "skipped", "reason": "No notes or transcript available to summarize"}

        try:
            resp = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize this meeting:\n\n{text[:8000]}"},
                ],
                temperature=0.2,
                max_completion_tokens=500,
            )
            summary = (resp.choices[0].message.content or "").strip()
        except Exception:
            logger.exception("LLM summary generation failed for meeting %s", meeting_id)
            return {"status": "failed", "reason": "LLM call failed"}

        if not summary:
            return {"status": "failed", "reason": "LLM returned empty response"}

        meeting.summary = summary
        await session.commit()

    return {"status": "success", "summary": summary}


class EntityExtractionAgent(BaseAgent):
    name = "entity_extraction"
    description = "Extracts entities and action items from meetings using GPT-4o"
    pipeline = "sync"
    dependencies = ["meeting_sync"]
    required_mcp_providers = []

    async def should_run(self, state: AgentState) -> bool:
        if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
            logger.info("No OpenAI key, skipping entity extraction")
            return False
        new_ids = state.get("new_meeting_ids", [])
        updated_ids = state.get("updated_meeting_ids", [])
        return len(new_ids) + len(updated_ids) > 0

    async def process(self, state: AgentState) -> AgentState:
        meeting_ids = list(state.get("new_meeting_ids", []))
        meeting_ids.extend(state.get("updated_meeting_ids", []))

        result = await extract_entities_for_meetings(meeting_ids)
        errors = list(state.get("errors", []))
        for e in result.get("errors", []):
            errors.append({"agent": self.name, **e})

        return {
            **state,
            "extracted_entities": [{"count": result.get("entities", 0)}],
            "resolved_entities": [],
            "extracted_action_items": [{"count": result.get("action_items", 0)}],
            "errors": errors,
        }
