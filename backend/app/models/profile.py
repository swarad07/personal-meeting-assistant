import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    traits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    learning_log: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('self', 'contact', 'org')",
            name="ck_profiles_type",
        ),
    )
