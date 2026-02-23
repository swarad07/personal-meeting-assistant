from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    granola_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[datetime] = mapped_column(nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_notes: Mapped[str] = mapped_column(Text, nullable=False)
    enhanced_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_call_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_vector: Mapped[None] = mapped_column(TSVECTOR, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sync_source: Mapped[str | None] = mapped_column(String(16), nullable=True)

    transcript_chunks: Mapped[list[TranscriptChunk]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    attendees: Mapped[list[Attendee]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_meetings_search_vector", "search_vector", postgresql_using="gin"),
    )


class TranscriptChunk(TimestampMixin, Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    search_vector: Mapped[None] = mapped_column(TSVECTOR, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="transcript_chunks")

    __table_args__ = (
        Index(
            "ix_transcript_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )


class Attendee(TimestampMixin, Base):
    __tablename__ = "attendees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="attendees")
