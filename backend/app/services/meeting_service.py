from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Attendee, Meeting, TranscriptChunk


class MeetingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_meetings(self, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        total_stmt = select(func.count()).select_from(Meeting)
        total = (await self.session.execute(total_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(Meeting)
            .options(selectinload(Meeting.attendees), selectinload(Meeting.action_items))
            .order_by(Meeting.date.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        meetings = result.scalars().all()

        return {
            "items": [self._meeting_to_dict(m) for m in meetings],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    async def get_meeting(self, meeting_id: str) -> dict[str, Any] | None:
        stmt = (
            select(Meeting)
            .options(
                selectinload(Meeting.attendees),
                selectinload(Meeting.transcript_chunks),
                selectinload(Meeting.action_items),
            )
            .where(Meeting.id == meeting_id)
        )
        result = await self.session.execute(stmt)
        meeting = result.scalar_one_or_none()
        if not meeting:
            return None
        return self._meeting_detail_to_dict(meeting)

    async def upsert_meeting(self, meeting_data: dict[str, Any]) -> str:
        granola_id = meeting_data.get("granola_id")
        meeting = None

        if granola_id:
            stmt = select(Meeting).where(Meeting.granola_id == granola_id)
            result = await self.session.execute(stmt)
            meeting = result.scalar_one_or_none()

        if meeting:
            meeting.title = meeting_data.get("title", meeting.title)
            meeting.raw_notes = meeting_data.get("raw_notes", meeting.raw_notes)
            meeting.enhanced_notes = meeting_data.get("enhanced_notes", meeting.enhanced_notes)
            meeting.summary = meeting_data.get("summary", meeting.summary)
            if meeting_data.get("duration") is not None:
                meeting.duration = meeting_data["duration"]
            meeting.synced_at = datetime.utcnow()
            meeting.sync_source = meeting_data.get("sync_source", meeting.sync_source)
        else:
            meeting = Meeting(
                id=uuid.uuid4(),
                granola_id=granola_id,
                title=meeting_data["title"],
                date=meeting_data["date"],
                duration=meeting_data.get("duration"),
                raw_notes=meeting_data.get("raw_notes") or "",
                enhanced_notes=meeting_data.get("enhanced_notes"),
                summary=meeting_data.get("summary"),
                synced_at=datetime.utcnow(),
                sync_source=meeting_data.get("sync_source"),
            )
            self.session.add(meeting)

        await self.session.flush()

        if "attendees" in meeting_data:
            from sqlalchemy import delete
            await self.session.execute(
                delete(Attendee).where(Attendee.meeting_id == meeting.id)
            )
            for att_data in meeting_data["attendees"]:
                attendee = Attendee(
                    meeting_id=meeting.id,
                    name=att_data["name"],
                    email=att_data.get("email"),
                    role=att_data.get("role"),
                )
                self.session.add(attendee)

        await self.session.flush()
        return str(meeting.id)

    async def meeting_exists_by_granola_id(self, granola_id: str) -> bool:
        stmt = select(func.count()).select_from(Meeting).where(Meeting.granola_id == granola_id)
        count = (await self.session.execute(stmt)).scalar() or 0
        return count > 0

    async def store_transcript_chunks(
        self, meeting_id: str, chunks: list[dict[str, Any]]
    ) -> int:
        from sqlalchemy import delete
        await self.session.execute(
            delete(TranscriptChunk).where(TranscriptChunk.meeting_id == uuid.UUID(meeting_id))
        )
        for chunk_data in chunks:
            chunk = TranscriptChunk(
                meeting_id=uuid.UUID(meeting_id),
                chunk_index=chunk_data["chunk_index"],
                speaker=chunk_data.get("speaker"),
                content=chunk_data["content"],
                start_time=chunk_data.get("start_time"),
                end_time=chunk_data.get("end_time"),
            )
            self.session.add(chunk)
        await self.session.flush()
        return len(chunks)

    async def update_meeting_embedding(
        self, meeting_id: str, embedding: list[float]
    ) -> None:
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        result = await self.session.execute(stmt)
        meeting = result.scalar_one_or_none()
        if meeting:
            meeting.embedding = embedding
            await self.session.flush()

    def _meeting_to_dict(self, m: Meeting) -> dict[str, Any]:
        return {
            "id": str(m.id),
            "granola_id": m.granola_id,
            "title": m.title,
            "date": m.date.isoformat(),
            "duration": m.duration,
            "summary": m.summary,
            "synced_at": m.synced_at.isoformat() if m.synced_at else None,
            "sync_source": m.sync_source,
            "attendees": [
                {"id": str(a.id), "name": a.name, "email": a.email, "role": a.role}
                for a in (m.attendees or [])
            ],
            "action_items_count": len(m.action_items) if m.action_items else 0,
        }

    def _meeting_detail_to_dict(self, m: Meeting) -> dict[str, Any]:
        d = self._meeting_to_dict(m)
        d["raw_notes"] = m.raw_notes
        d["enhanced_notes"] = m.enhanced_notes
        d["next_call_brief"] = m.next_call_brief
        d["transcript_chunks"] = sorted(
            [
                {
                    "id": str(c.id),
                    "chunk_index": c.chunk_index,
                    "speaker": c.speaker,
                    "content": c.content,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                }
                for c in (m.transcript_chunks or [])
            ],
            key=lambda x: x["chunk_index"],
        )
        d["action_items"] = [
            {
                "id": str(ai.id),
                "assignee": ai.assignee,
                "description": ai.description,
                "status": ai.status,
                "due_date": ai.due_date.isoformat() if ai.due_date else None,
            }
            for ai in (m.action_items or [])
        ]
        return d
