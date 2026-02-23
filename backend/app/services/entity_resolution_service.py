from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from app.models.profile import Profile
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class EntityResolutionService:
    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService) -> None:
        self.session = session
        self.embedding_service = embedding_service

    async def resolve(self, raw_mention: dict[str, Any], meeting_id: str) -> dict[str, Any]:
        """Resolve a raw entity mention to a canonical entity.

        Returns dict with 'entity_id', 'name', 'type', 'is_new'.
        Pipeline: exact match -> fuzzy match -> embedding match -> create new.
        (LLM fallback omitted for cost; can be added later.)
        """
        name = raw_mention.get("name", "").strip()
        email = raw_mention.get("email")
        entity_type = raw_mention.get("entity_type", "contact")

        if not name:
            entity_id = str(uuid.uuid4())
            return {"entity_id": entity_id, "name": "Unknown", "type": entity_type, "is_new": True}

        match = await self.exact_match(name, email)
        if match:
            return {**match, "is_new": False}

        match = await self.fuzzy_match(name)
        if match:
            return {**match, "is_new": False}

        match = await self.embedding_match(name)
        if match:
            return {**match, "is_new": False}

        entity_id = str(uuid.uuid4())
        profile = Profile(
            id=uuid.UUID(entity_id),
            type=entity_type,
            name=name,
            email=email or "",
            bio=None,
        )
        self.session.add(profile)
        await self.session.flush()

        logger.info("Created new entity: %s (%s)", name, entity_id)
        return {"entity_id": entity_id, "name": name, "type": entity_type, "is_new": True}

    async def exact_match(self, name: str, email: str | None) -> dict[str, Any] | None:
        if email:
            stmt = select(Profile).where(
                func.lower(Profile.email) == email.lower()
            )
            result = await self.session.execute(stmt)
            profile = result.scalar_one_or_none()
            if profile:
                return {
                    "entity_id": str(profile.id),
                    "name": profile.name,
                    "type": profile.type,
                }

        stmt = select(Profile).where(
            func.lower(Profile.name) == name.lower()
        )
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            return {
                "entity_id": str(profile.id),
                "name": profile.name,
                "type": profile.type,
            }

        return None

    async def fuzzy_match(self, name: str, threshold: float = 85) -> dict[str, Any] | None:
        stmt = select(Profile).where(Profile.type.in_(["contact", "self", "org"]))
        result = await self.session.execute(stmt)
        profiles = result.scalars().all()

        best_match = None
        best_score = 0

        for profile in profiles:
            score = fuzz.ratio(name.lower(), profile.name.lower())
            if score >= threshold and score > best_score:
                best_score = score
                best_match = profile

        if best_match:
            logger.info("Fuzzy matched '%s' -> '%s' (score=%d)", name, best_match.name, best_score)
            return {
                "entity_id": str(best_match.id),
                "name": best_match.name,
                "type": best_match.type,
            }

        return None

    async def embedding_match(
        self, text: str, threshold: float = 0.88
    ) -> dict[str, Any] | None:
        try:
            embedding = await self.embedding_service.embed_text(text)
        except Exception:
            logger.warning("Embedding generation failed for entity resolution, skipping")
            return None

        stmt = text("""
            SELECT id, name, type, embedding <=> :embedding AS distance
            FROM profiles
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :embedding
            LIMIT 1
        """)

        result = await self.session.execute(
            stmt, {"embedding": str(embedding)}
        )
        row = result.first()

        if row and (1 - row.distance) >= threshold:
            logger.info(
                "Embedding matched '%s' -> '%s' (similarity=%.3f)",
                text, row.name, 1 - row.distance,
            )
            return {
                "entity_id": str(row.id),
                "name": row.name,
                "type": row.type,
            }

        return None

    async def merge_entities(self, source_id: str, target_id: str) -> None:
        """Merge source entity into target. Updates all references."""
        raise NotImplementedError("Manual merge not yet implemented")
