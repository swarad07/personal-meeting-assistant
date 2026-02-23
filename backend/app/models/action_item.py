from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ActionItem(TimestampMixin, Base):
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    assignee: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="open")
    due_date: Mapped[date | None] = mapped_column(nullable=True)

    meeting: Mapped["Meeting"] = relationship(back_populates="action_items")

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'done', 'dismissed')",
            name="ck_action_items_status",
        ),
    )
