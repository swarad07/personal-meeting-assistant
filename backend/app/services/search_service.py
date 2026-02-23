from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import EmbeddingService
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        neo4j_driver: AsyncDriver,
        embedding_service: EmbeddingService,
    ) -> None:
        self.session = session
        self.neo4j_driver = neo4j_driver
        self.embedding_service = embedding_service

    async def hybrid_search(
        self, query: str, page: int = 1, page_size: int = 20
    ) -> dict[str, Any]:
        fts_results = await self.full_text_search(query, limit=50)
        sem_results = await self.semantic_search(query, limit=50)
        graph_results = await self.graph_search(query, limit=50)

        merged = self.reciprocal_rank_fusion(fts_results, sem_results, graph_results)

        start = (page - 1) * page_size
        paginated = merged[start : start + page_size]

        return {
            "results": paginated,
            "total": len(merged),
            "synthesis": None,
        }

    async def full_text_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        words = [w for w in query.split() if w.strip()]
        ts_query = " | ".join(words) if words else query

        meeting_sql = text("""
            SELECT
                m.id::text as meeting_id,
                m.title,
                m.date::text as date,
                ts_rank_cd(m.search_vector, to_tsquery('english', :q)) as rank,
                ts_headline('english', m.raw_notes, to_tsquery('english', :q),
                    'MaxWords=40, MinWords=20, StartSel=**, StopSel=**') as snippet
            FROM meetings m
            WHERE m.search_vector @@ to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        chunk_sql = text("""
            SELECT
                tc.meeting_id::text as meeting_id,
                m.title,
                m.date::text as date,
                ts_rank_cd(tc.search_vector, to_tsquery('english', :q)) as rank,
                ts_headline('english', tc.content, to_tsquery('english', :q),
                    'MaxWords=40, MinWords=20, StartSel=**, StopSel=**') as snippet
            FROM transcript_chunks tc
            JOIN meetings m ON m.id = tc.meeting_id
            WHERE tc.search_vector @@ to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            meeting_result = await self.session.execute(meeting_sql, {"q": ts_query, "limit": limit})
            for row in meeting_result:
                if row.meeting_id not in seen:
                    seen.add(row.meeting_id)
                    results.append({
                        "meeting_id": row.meeting_id,
                        "title": row.title,
                        "date": row.date,
                        "snippet": row.snippet or "",
                        "score": float(row.rank),
                        "source": "fulltext",
                    })
        except Exception:
            logger.debug("Full-text search on meetings failed (search_vector may not be populated)")

        try:
            chunk_result = await self.session.execute(chunk_sql, {"q": ts_query, "limit": limit})
            for row in chunk_result:
                if row.meeting_id not in seen:
                    seen.add(row.meeting_id)
                    results.append({
                        "meeting_id": row.meeting_id,
                        "title": row.title,
                        "date": row.date,
                        "snippet": row.snippet or "",
                        "score": float(row.rank),
                        "source": "fulltext",
                    })
        except Exception:
            logger.debug("Full-text search on transcript_chunks failed (search_vector may not be populated)")

        if not results:
            fallback_sql = text("""
                SELECT
                    m.id::text as meeting_id,
                    m.title,
                    m.date::text as date,
                    CASE WHEN m.raw_notes ILIKE :pattern THEN 1.0 ELSE 0.5 END as rank,
                    SUBSTRING(m.raw_notes, 1, 200) as snippet
                FROM meetings m
                WHERE m.raw_notes ILIKE :pattern
                   OR m.title ILIKE :pattern
                   OR m.summary ILIKE :pattern
                ORDER BY m.date DESC
                LIMIT :limit
            """)
            try:
                fallback_result = await self.session.execute(
                    fallback_sql, {"pattern": f"%{query}%", "limit": limit}
                )
                for row in fallback_result:
                    results.append({
                        "meeting_id": row.meeting_id,
                        "title": row.title,
                        "date": row.date,
                        "snippet": row.snippet or "",
                        "score": float(row.rank),
                        "source": "fulltext",
                    })
            except Exception:
                logger.debug("ILIKE fallback search failed")

        return results

    async def semantic_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            query_embedding = await self.embedding_service.embed_text(query)
        except Exception:
            logger.warning("Failed to generate query embedding, skipping semantic search")
            return []

        meeting_sql = text("""
            SELECT
                m.id::text as meeting_id,
                m.title,
                m.date::text as date,
                SUBSTRING(m.raw_notes, 1, 200) as snippet,
                1 - (m.embedding <=> :embedding::vector) as similarity
            FROM meetings m
            WHERE m.embedding IS NOT NULL
            ORDER BY m.embedding <=> :embedding::vector
            LIMIT :limit
        """)

        chunk_sql = text("""
            SELECT
                tc.meeting_id::text as meeting_id,
                m.title,
                m.date::text as date,
                SUBSTRING(tc.content, 1, 200) as snippet,
                1 - (tc.embedding <=> :embedding::vector) as similarity
            FROM transcript_chunks tc
            JOIN meetings m ON m.id = tc.meeting_id
            WHERE tc.embedding IS NOT NULL
            ORDER BY tc.embedding <=> :embedding::vector
            LIMIT :limit
        """)

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        emb_str = str(query_embedding)

        try:
            meeting_result = await self.session.execute(
                meeting_sql, {"embedding": emb_str, "limit": limit}
            )
            for row in meeting_result:
                if row.meeting_id not in seen and row.similarity > 0.3:
                    seen.add(row.meeting_id)
                    results.append({
                        "meeting_id": row.meeting_id,
                        "title": row.title,
                        "date": row.date,
                        "snippet": row.snippet or "",
                        "score": float(row.similarity),
                        "source": "semantic",
                    })
        except Exception:
            logger.debug("Semantic search on meetings failed (no embeddings populated yet)")

        try:
            chunk_result = await self.session.execute(
                chunk_sql, {"embedding": emb_str, "limit": limit}
            )
            for row in chunk_result:
                if row.meeting_id not in seen and row.similarity > 0.3:
                    seen.add(row.meeting_id)
                    results.append({
                        "meeting_id": row.meeting_id,
                        "title": row.title,
                        "date": row.date,
                        "snippet": row.snippet or "",
                        "score": float(row.similarity),
                        "source": "semantic",
                    })
        except Exception:
            logger.debug("Semantic search on transcript_chunks failed (no embeddings populated yet)")

        return results

    async def graph_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        neo4j_service = Neo4jService(self.neo4j_driver)

        try:
            entities = await neo4j_service.search_entities_by_name(query, limit=5)
        except Exception:
            logger.debug("Neo4j entity search failed")
            return []

        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for entity in entities:
            try:
                meeting_ids = await neo4j_service.find_meetings_for_entity(entity["id"])
                for mid in meeting_ids:
                    if mid not in seen:
                        seen.add(mid)
                        results.append({
                            "meeting_id": mid,
                            "title": f"Related to {entity['name']}",
                            "date": "",
                            "snippet": f"Connected via {entity['type']}: {entity['name']}",
                            "score": 0.8,
                            "source": "graph",
                        })
            except Exception:
                continue

        return results[:limit]

    def reciprocal_rank_fusion(
        self, *result_lists: list[dict[str, Any]], k: int = 60
    ) -> list[dict[str, Any]]:
        scores: dict[str, float] = {}
        best_result: dict[str, dict] = {}

        for results in result_lists:
            for rank, result in enumerate(results):
                mid = result["meeting_id"]
                rrf_score = 1.0 / (k + rank + 1)
                scores[mid] = scores.get(mid, 0) + rrf_score

                if mid not in best_result or result.get("score", 0) > best_result[mid].get("score", 0):
                    best_result[mid] = result

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        output: list[dict[str, Any]] = []
        for mid, rrf_score in ranked:
            entry = dict(best_result[mid])
            entry["score"] = round(rrf_score, 6)
            output.append(entry)

        return output
