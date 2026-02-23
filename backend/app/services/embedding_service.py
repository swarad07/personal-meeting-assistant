from __future__ import annotations

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_embedding_model
        self._client: AsyncOpenAI | None = None
        self._semaphore = asyncio.Semaphore(settings.openai_max_concurrent)

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        text = text.strip()
        if not text:
            return [0.0] * 1536

        async with self._semaphore:
            resp = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return resp.data[0].embedding

    async def embed_batch(
        self, texts: list[str], batch_size: int = 100
    ) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t.strip() for t in texts[i : i + batch_size]]
            batch = [t if t else "empty" for t in batch]

            async with self._semaphore:
                resp = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                results.extend([d.embedding for d in resp.data])

        return results


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
