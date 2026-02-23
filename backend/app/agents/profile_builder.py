"""ProfileBuilderAgent: Builds and updates profiles from attendee data and meeting history.

Standalone runner build_profiles_from_meetings() creates profiles for all attendees
found in PostgreSQL meetings. After the basic pass, enrich_profiles_with_llm()
generates rich bios for profiles that lack one, using transcript data, action items,
and meeting context from GPT-4o.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentState, BaseAgent
from app.config import settings
from app.models.action_item import ActionItem
from app.models.meeting import Attendee, Meeting, TranscriptChunk
from app.models.profile import Profile

logger = logging.getLogger(__name__)

BIO_SYSTEM_PROMPT = """You are a professional profiler. Given meeting transcripts, notes, and action items involving a person, write a rich professional bio paragraph (3-6 sentences).

Cover:
- Their likely role or job function
- Areas of expertise or topics they frequently discuss
- Communication style and personality (if observable)
- Key projects or initiatives they are involved in

Do NOT invent facts not supported by the data. If information is sparse, keep the bio shorter.
Return ONLY the bio paragraph text, no JSON, no markdown."""


async def ensure_attendee_profiles() -> dict[str, Any]:
    """Fast pass: guarantee every meeting attendee has a profile. No LLM calls."""
    from app.db.postgres import async_session_factory

    created = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        attendees_stmt = (
            select(
                Attendee.name,
                Attendee.email,
                func.count(Attendee.meeting_id.distinct()).label("meeting_count"),
                func.max(Meeting.date).label("last_seen"),
                func.min(Meeting.date).label("first_seen"),
            )
            .join(Meeting, Attendee.meeting_id == Meeting.id)
            .group_by(Attendee.name, Attendee.email)
        )
        result = await session.execute(attendees_stmt)
        attendee_rows = result.all()

        logger.info("Found %d unique attendees across meetings", len(attendee_rows))

        for row in attendee_rows:
            name = row.name
            email = row.email
            meeting_count = row.meeting_count
            last_seen = row.last_seen
            first_seen = row.first_seen

            try:
                profile = None
                if email:
                    stmt = select(Profile).where(func.lower(Profile.email) == email.lower())
                    res = await session.execute(stmt)
                    profile = res.scalar_one_or_none()

                if not profile:
                    stmt = select(Profile).where(func.lower(Profile.name) == name.lower())
                    res = await session.execute(stmt)
                    profile = res.scalar_one_or_none()

                if profile:
                    traits = profile.traits or {}
                    traits["meeting_count"] = meeting_count
                    traits["last_seen"] = last_seen.isoformat() if last_seen else None
                    traits["first_seen"] = first_seen.isoformat() if first_seen else None
                    profile.traits = traits
                    if email and not profile.email:
                        profile.email = email
                    updated += 1
                else:
                    profile = Profile(
                        id=uuid.uuid4(),
                        type="contact",
                        name=name,
                        email=email,
                        bio=None,
                        traits={
                            "meeting_count": meeting_count,
                            "last_seen": last_seen.isoformat() if last_seen else None,
                            "first_seen": first_seen.isoformat() if first_seen else None,
                        },
                    )
                    session.add(profile)
                    created += 1

            except Exception as e:
                logger.warning("Profile build failed for %s: %s", name, e)
                errors.append({"name": name, "error": str(e)})

        self_stmt = select(Profile).where(Profile.type == "self")
        res = await session.execute(self_stmt)
        if res.scalar_one_or_none() is None:
            session.add(Profile(
                id=uuid.uuid4(),
                type="self",
                name="Me",
                bio="Your personal profile. Enriched as you use the system.",
                traits={"meeting_count": 0},
                learning_log=[],
            ))
            created += 1

        await session.commit()

    logger.info("Profiles ensured: %d created, %d updated, %d errors", created, updated, len(errors))
    return {"created": created, "updated": updated, "errors": errors}


async def build_profiles_from_meetings() -> dict[str, Any]:
    """Full profile builder — ensures all attendees have profiles, then enriches with LLM."""
    result = await ensure_attendee_profiles()
    created = result["created"]
    updated = result["updated"]
    errors = list(result["errors"])
    enriched = 0

    if settings.openai_api_key and settings.openai_api_key != "sk-your-key-here":
        try:
            enriched = await enrich_profiles_with_llm()
        except Exception as e:
            logger.warning("LLM profile enrichment failed: %s", e)
            errors.append({"name": "_enrichment", "error": str(e)})

    logger.info(
        "Profiles: %d created, %d updated, %d enriched, %d errors",
        created, updated, enriched, len(errors),
    )
    return {"created": created, "updated": updated, "enriched": enriched, "errors": errors}


async def enrich_profiles_with_llm(limit: int = 10) -> int:
    """Generate bios for profiles that don't have one yet."""
    from openai import AsyncOpenAI
    from app.db.postgres import async_session_factory

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    enriched = 0

    async with async_session_factory() as session:
        profiles_stmt = (
            select(Profile)
            .where(
                Profile.type == "contact",
                Profile.bio.is_(None),
            )
            .order_by(Profile.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(profiles_stmt)
        profiles = result.scalars().all()

        if not profiles:
            logger.info("No profiles need bio enrichment")
            return 0

        logger.info("Enriching bios for %d profiles", len(profiles))

    for profile in profiles:
        try:
            context = await _gather_profile_context(profile)
            if not context.strip():
                continue

            bio = await _generate_bio(client, profile.name, context)
            if not bio:
                continue

            async with async_session_factory() as session:
                stmt = select(Profile).where(Profile.id == profile.id)
                res = await session.execute(stmt)
                p = res.scalar_one_or_none()
                if p:
                    p.bio = bio
                    log_entry = {
                        "type": "bio_generated",
                        "timestamp": datetime.utcnow().isoformat(),
                        "context_length": len(context),
                    }
                    existing_log = p.learning_log or []
                    if isinstance(existing_log, list):
                        existing_log.append(log_entry)
                    else:
                        existing_log = [log_entry]
                    p.learning_log = existing_log
                    await session.commit()
                    enriched += 1

        except Exception as e:
            logger.warning("Bio enrichment failed for %s: %s", profile.name, e)

    return enriched


async def _gather_profile_context(profile: Profile) -> str:
    """Collect transcript segments, meeting info, and action items for a person."""
    from app.db.postgres import async_session_factory

    parts: list[str] = []

    async with async_session_factory() as session:
        transcript_stmt = (
            select(TranscriptChunk.content, Meeting.title, Meeting.date)
            .join(Meeting, TranscriptChunk.meeting_id == Meeting.id)
            .where(func.lower(TranscriptChunk.speaker) == profile.name.lower())
            .order_by(Meeting.date.desc())
            .limit(60)
        )
        result = await session.execute(transcript_stmt)
        transcript_rows = result.all()

        if transcript_rows:
            parts.append(f"Transcript segments where {profile.name} spoke:")
            for content, mtitle, mdate in transcript_rows[:40]:
                date_str = mdate.strftime("%Y-%m-%d") if mdate else ""
                parts.append(f"  [{mtitle} - {date_str}]: {content[:200]}")

        meetings_stmt = (
            select(Meeting.title, Meeting.date, Meeting.summary)
            .join(Attendee, Attendee.meeting_id == Meeting.id)
            .where(func.lower(Attendee.name) == profile.name.lower())
            .order_by(Meeting.date.desc())
            .limit(15)
        )
        result = await session.execute(meetings_stmt)
        meeting_rows = result.all()

        if meeting_rows:
            parts.append(f"\nMeetings attended by {profile.name}:")
            for mtitle, mdate, msummary in meeting_rows:
                date_str = mdate.strftime("%Y-%m-%d") if mdate else ""
                line = f"  [{date_str}] {mtitle}"
                if msummary:
                    line += f" — {msummary[:150]}"
                parts.append(line)

        action_stmt = (
            select(ActionItem.description, ActionItem.status)
            .where(func.lower(ActionItem.assignee) == profile.name.lower())
            .limit(10)
        )
        result = await session.execute(action_stmt)
        action_rows = result.all()

        if action_rows:
            parts.append(f"\nAction items assigned to {profile.name}:")
            for desc, status in action_rows:
                parts.append(f"  [{status}] {desc}")

    return "\n".join(parts)


async def _generate_bio(client, name: str, context: str) -> str | None:
    """Call GPT to produce a bio paragraph."""
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": BIO_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Generate a professional bio for {name} based on this data:\n\n{context[:6000]}",
                },
            ],
            temperature=0.3,
            max_completion_tokens=400,
        )
        return (resp.choices[0].message.content or "").strip() or None
    except Exception:
        logger.exception("LLM bio generation failed for %s", name)
        return None


async def generate_bio_for_profile(profile_id: str) -> dict[str, Any]:
    """Generate or regenerate a bio for a single profile by ID."""
    from openai import AsyncOpenAI
    from app.db.postgres import async_session_factory

    if not settings.openai_api_key or settings.openai_api_key == "sk-your-key-here":
        raise RuntimeError("OpenAI API key not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with async_session_factory() as session:
        stmt = select(Profile).where(Profile.id == profile_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        if not profile:
            raise ValueError(f"Profile {profile_id} not found")

        context = await _gather_profile_context(profile)
        if not context.strip():
            return {"status": "skipped", "reason": "No meeting data available for this person"}

        bio = await _generate_bio(client, profile.name, context)
        if not bio:
            return {"status": "failed", "reason": "LLM did not return a bio"}

        profile.bio = bio
        log_entry = {
            "type": "bio_generated",
            "timestamp": datetime.utcnow().isoformat(),
            "context_length": len(context),
            "trigger": "manual",
        }
        existing_log = profile.learning_log or []
        if isinstance(existing_log, list):
            existing_log.append(log_entry)
        else:
            existing_log = [log_entry]
        profile.learning_log = existing_log
        await session.commit()

    return {"status": "success", "bio": bio}


class ProfileBuilderAgent(BaseAgent):
    name = "profile_builder"
    description = "Builds and enriches profiles from meeting data"
    pipeline = "sync"
    dependencies = ["relationship_builder"]
    required_mcp_providers = []

    async def should_run(self, state: AgentState) -> bool:
        return (
            len(state.get("new_meeting_ids", [])) > 0
            or len(state.get("updated_meeting_ids", [])) > 0
        )

    async def process(self, state: AgentState) -> AgentState:
        result = await build_profiles_from_meetings()
        errors = list(state.get("errors", []))
        for e in result.get("errors", []):
            errors.append({"agent": self.name, **e})
        return {**state, "errors": errors}
