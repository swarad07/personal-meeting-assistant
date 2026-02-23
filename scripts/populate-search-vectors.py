"""Populate tsvector search columns for existing meetings and transcript chunks.

This enables PostgreSQL full-text search without needing OpenAI.
Run after seeding data or any time you want to refresh search vectors.
"""

import asyncio

from sqlalchemy import text

from app.db.postgres import async_session_factory


async def populate():
    async with async_session_factory() as session:
        await session.execute(text("""
            UPDATE meetings
            SET search_vector = to_tsvector('english',
                coalesce(title, '') || ' ' ||
                coalesce(raw_notes, '') || ' ' ||
                coalesce(enhanced_notes, '') || ' ' ||
                coalesce(summary, '')
            )
            WHERE search_vector IS NULL
        """))

        await session.execute(text("""
            UPDATE transcript_chunks
            SET search_vector = to_tsvector('english',
                coalesce(speaker, '') || ' ' ||
                coalesce(content, '')
            )
            WHERE search_vector IS NULL
        """))

        await session.commit()

        meeting_count = (await session.execute(
            text("SELECT count(*) FROM meetings WHERE search_vector IS NOT NULL")
        )).scalar()
        chunk_count = (await session.execute(
            text("SELECT count(*) FROM transcript_chunks WHERE search_vector IS NOT NULL")
        )).scalar()

        print(f"Populated search vectors: {meeting_count} meetings, {chunk_count} transcript chunks")


if __name__ == "__main__":
    asyncio.run(populate())
