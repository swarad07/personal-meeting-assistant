import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentRunLog(TimestampMixin, Base):
    __tablename__ = "agent_run_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pipeline: Mapped[str] = mapped_column(String, nullable=False)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    trigger: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="running"
    )
    meetings_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    entities_extracted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    errors_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_agent_run_log_status",
        ),
    )
