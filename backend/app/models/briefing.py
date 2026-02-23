import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Briefing(TimestampMixin, Base):
    __tablename__ = "briefings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetings.id"), nullable=True
    )
    calendar_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attendee_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    action_items_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
