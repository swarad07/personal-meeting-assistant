from datetime import datetime

from pydantic import BaseModel


class AttendeeResponse(BaseModel):
    id: str
    name: str
    email: str | None = None
    role: str | None = None


class TranscriptChunkResponse(BaseModel):
    id: str
    chunk_index: int
    speaker: str | None = None
    content: str
    start_time: float | None = None
    end_time: float | None = None


class MeetingResponse(BaseModel):
    id: str
    granola_id: str | None = None
    title: str
    date: datetime
    duration: int | None = None
    summary: str | None = None
    synced_at: datetime | None = None
    attendees: list[AttendeeResponse] = []
    action_items_count: int = 0


class MeetingDetailResponse(MeetingResponse):
    raw_notes: str | None = None
    enhanced_notes: str | None = None
    transcript_chunks: list[TranscriptChunkResponse] = []
    action_items: list = []
    related_meeting_ids: list[str] = []
