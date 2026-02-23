from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class TranscriptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def chunk_transcript(
        self,
        meeting_id: str,
        transcript: str,
        speakers: list[str] | None = None,
    ) -> list[dict]:
        """Split transcript into ~2-3 min time-stamped chunks with speaker labels."""
        raise NotImplementedError

    async def store_chunks(self, meeting_id: str, chunks: list[dict]) -> int:
        """Store transcript chunks with embeddings and search vectors. Returns count."""
        raise NotImplementedError
