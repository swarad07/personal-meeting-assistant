"""MeetingSyncAgent: Fetches meetings from Granola local cache and stores them in PostgreSQL.

This is the first agent in the sync pipeline. It:
1. Reads from Granola's local cache via the GranolaProvider
2. Identifies new or updated meetings (by granola_id)
3. Upserts meetings into PostgreSQL with attendees
4. Fetches and chunks transcripts for downstream search/embedding

The sync_all_meetings() coroutine provides a standalone entry point that
bypasses LangGraph to avoid greenlet/async-session incompatibilities.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.agents.base import AgentState, BaseAgent

logger = logging.getLogger(__name__)

CHUNK_MAX_CHARS = 1500
CHUNK_OVERLAP_CHARS = 200


def _parse_time(val: Any) -> float | None:
    """Convert ISO timestamp string or numeric value to epoch seconds (float)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            return None
    return None


def chunk_transcript(transcript_text: str, speakers: list[dict] | None = None) -> list[dict[str, Any]]:
    """Split transcript into overlapping chunks for search and embeddings."""
    if speakers:
        chunks = []
        for i, segment in enumerate(speakers):
            text = segment.get("text", segment.get("content", ""))
            if not text or not text.strip():
                continue
            chunks.append({
                "chunk_index": i,
                "speaker": segment.get("speaker_name", segment.get("speaker")),
                "content": text.strip(),
                "start_time": _parse_time(segment.get("start_timestamp", segment.get("start_time"))),
                "end_time": _parse_time(segment.get("end_timestamp", segment.get("end_time"))),
            })
        return chunks

    if not transcript_text or not transcript_text.strip():
        return []

    chunks = []
    idx = 0
    start = 0
    while start < len(transcript_text):
        end = min(start + CHUNK_MAX_CHARS, len(transcript_text))
        if end < len(transcript_text):
            last_period = transcript_text.rfind(". ", start, end)
            last_newline = transcript_text.rfind("\n", start, end)
            break_point = max(last_period, last_newline)
            if break_point > start:
                end = break_point + 1

        chunks.append({
            "chunk_index": idx,
            "speaker": None,
            "content": transcript_text[start:end].strip(),
            "start_time": None,
            "end_time": None,
        })
        idx += 1
        start = end - CHUNK_OVERLAP_CHARS if end < len(transcript_text) else end

    return chunks


def _compute_duration_minutes(start_str: str | None, end_str: str | None) -> int | None:
    """Return meeting duration in minutes from ISO start/end timestamps."""
    if not start_str or not end_str:
        return None
    try:
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        delta = (end_dt - start_dt).total_seconds()
        return max(1, int(delta / 60)) if delta > 0 else None
    except (ValueError, TypeError):
        return None


def normalize_meeting(detail: dict[str, Any], granola_id: str) -> dict[str, Any]:
    """Parse a Granola document into a flat meeting dict ready for DB upsert."""
    attendees = []
    for att in detail.get("attendees", []):
        if isinstance(att, dict):
            attendees.append({
                "name": att.get("name", att.get("email", "Unknown")),
                "email": att.get("email"),
                "role": None,
            })

    date_str = detail.get("start") or detail.get("created_at")
    if isinstance(date_str, str):
        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            date = datetime.utcnow()
    else:
        date = datetime.utcnow()

    notes_md = detail.get("notes_markdown", "")
    notes_plain = detail.get("notes_plain", "")
    title = detail.get("title") or f"Meeting {granola_id[:8]}"

    duration = _compute_duration_minutes(
        detail.get("start"), detail.get("end")
    )

    return {
        "granola_id": granola_id,
        "title": title,
        "date": date,
        "duration": duration,
        "raw_notes": notes_md or notes_plain or "",
        "enhanced_notes": detail.get("overview"),
        "summary": detail.get("summary"),
        "attendees": attendees,
    }


async def sync_all_meetings(granola_provider: Any) -> dict[str, Any]:
    """Standalone sync that runs outside LangGraph to avoid greenlet issues."""
    from app.db.postgres import async_session_factory
    from app.services.meeting_service import MeetingService

    new_ids: list[str] = []
    updated_ids: list[str] = []
    skipped_ids: list[str] = []
    errors: list[dict[str, Any]] = []

    try:
        meetings_list = await granola_provider.execute_tool("list-documents", {"limit": 500})
    except Exception as e:
        return {"new": 0, "updated": 0, "skipped": 0, "errors": [str(e)]}

    if not isinstance(meetings_list, list):
        meetings_list = []

    logger.info("Granola returned %d meetings to sync", len(meetings_list))

    for meeting_data in meetings_list:
        granola_id = meeting_data.get("id")
        if not granola_id:
            continue

        try:
            async with async_session_factory() as session:
                svc = MeetingService(session)
                exists = await svc.meeting_exists_by_granola_id(granola_id)

                detail = await granola_provider.execute_tool(
                    "get-document", {"documentId": granola_id}
                )
                if not detail:
                    skipped_ids.append(granola_id)
                    continue

                sync_source = getattr(granola_provider, "last_source", "unknown")
                parsed = normalize_meeting(detail, granola_id)
                parsed["sync_source"] = sync_source
                meeting_id = await svc.upsert_meeting(parsed)

                transcript_segments = await granola_provider.execute_tool(
                    "get-transcript", {"documentId": granola_id}
                )
                if isinstance(transcript_segments, list) and transcript_segments:
                    chunks = chunk_transcript("", speakers=transcript_segments)
                elif parsed.get("raw_notes"):
                    chunks = chunk_transcript(parsed["raw_notes"])
                else:
                    chunks = []

                if chunks:
                    await svc.store_transcript_chunks(meeting_id, chunks)

                await session.commit()

                if exists:
                    updated_ids.append(meeting_id)
                else:
                    new_ids.append(meeting_id)

        except Exception as e:
            logger.warning("Failed to sync meeting %s: %s", granola_id, e)
            errors.append({"granola_id": granola_id, "error": str(e)})

    logger.info(
        "Sync complete: %d new, %d updated, %d skipped, %d errors",
        len(new_ids), len(updated_ids), len(skipped_ids), len(errors),
    )

    if new_ids or updated_ids:
        try:
            from app.agents.profile_builder import ensure_attendee_profiles
            profile_result = await ensure_attendee_profiles()
            logger.info(
                "Post-sync profiles: %d created, %d updated",
                profile_result["created"], profile_result["updated"],
            )
        except Exception as e:
            logger.warning("Post-sync profile creation failed: %s", e)

    return {
        "new": len(new_ids),
        "updated": len(updated_ids),
        "skipped": len(skipped_ids),
        "errors": errors,
        "new_meeting_ids": new_ids,
        "updated_meeting_ids": updated_ids,
    }


async def resync_single_meeting(meeting_id: str, mcp_registry: Any) -> dict[str, Any]:
    """Re-fetch notes and transcript for a single meeting from Granola."""
    from app.db.postgres import async_session_factory
    from app.services.meeting_service import MeetingService

    granola = mcp_registry.get("granola")

    async with async_session_factory() as session:
        svc = MeetingService(session)
        meeting_data = await svc.get_meeting(meeting_id)
        if not meeting_data:
            raise ValueError(f"Meeting {meeting_id} not found")

        granola_id = meeting_data.get("granola_id")
        if not granola_id:
            raise ValueError("Meeting has no Granola ID, cannot re-sync")

        detail = await granola.execute_tool("get-document", {"documentId": granola_id})
        if not detail:
            raise RuntimeError("Granola returned no data for this meeting")

        sync_source = getattr(granola, "last_source", "unknown")
        parsed = normalize_meeting(detail, granola_id)
        parsed["sync_source"] = sync_source
        await svc.upsert_meeting(parsed)

        transcript_segments = await granola.execute_tool(
            "get-transcript", {"documentId": granola_id}
        )
        chunks_stored = 0
        if isinstance(transcript_segments, list) and transcript_segments:
            chunks = chunk_transcript("", speakers=transcript_segments)
            if chunks:
                chunks_stored = await svc.store_transcript_chunks(meeting_id, chunks)
        elif parsed.get("raw_notes"):
            chunks = chunk_transcript(parsed["raw_notes"])
            if chunks:
                chunks_stored = await svc.store_transcript_chunks(meeting_id, chunks)

        await session.commit()

    return {
        "status": "success",
        "title": parsed.get("title"),
        "has_notes": bool(parsed.get("raw_notes")),
        "has_summary": bool(parsed.get("summary")),
        "transcript_chunks": chunks_stored,
        "sync_source": sync_source,
    }


class MeetingSyncAgent(BaseAgent):
    """LangGraph-compatible wrapper. Delegates to sync_all_meetings()."""

    name = "meeting_sync"
    description = "Syncs meetings from Granola local cache into PostgreSQL"
    pipeline = "sync"
    dependencies = []
    required_mcp_providers = ["granola"]

    async def should_run(self, state: AgentState) -> bool:
        mcp_registry = state.get("mcp_registry")
        if not mcp_registry:
            return False
        try:
            provider = mcp_registry.get("granola")
            from app.mcp.base import ProviderStatus
            return (await provider.health_check()) == ProviderStatus.HEALTHY
        except (KeyError, Exception):
            return False

    async def process(self, state: AgentState) -> AgentState:
        mcp_registry = state["mcp_registry"]
        granola = mcp_registry.get("granola")
        result = await sync_all_meetings(granola)

        errors = list(state.get("errors", []))
        for e in result.get("errors", []):
            errors.append({"agent": self.name, **e})

        return {
            **state,
            "new_meeting_ids": result.get("new_meeting_ids", []),
            "updated_meeting_ids": result.get("updated_meeting_ids", []),
            "skipped_meeting_ids": [],
            "errors": errors,
        }
