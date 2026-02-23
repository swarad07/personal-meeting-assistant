"""RelationshipBuilderAgent: Creates Neo4j relationships from meeting co-occurrence.

Standalone runner build_relationships_from_meetings() analyses which people appear
together in meetings and creates KNOWS, ATTENDED, and other relationships in Neo4j.
No OpenAI required — purely structural co-occurrence analysis.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentState, BaseAgent
from app.models.meeting import Attendee, Meeting
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


async def build_relationships_from_meetings() -> dict[str, Any]:
    """Standalone relationship builder — co-occurrence analysis from attendee data."""
    from app.db.neo4j_driver import get_neo4j_driver
    from app.db.postgres import async_session_factory

    driver = await get_neo4j_driver()
    neo4j_svc = Neo4jService(driver)

    new_rels = 0
    strengthened = 0
    meetings_processed = 0
    errors: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        meetings_stmt = select(Meeting.id, Meeting.title, Meeting.date).order_by(Meeting.date)
        result = await session.execute(meetings_stmt)
        meetings = result.all()

        logger.info("Building relationships from %d meetings", len(meetings))

        for meeting_id, title, date in meetings:
            try:
                await neo4j_svc.create_meeting_node(
                    meeting_id=str(meeting_id),
                    title=title or "",
                    date=date.isoformat() if date else "",
                )

                att_stmt = select(Attendee.name, Attendee.email).where(
                    Attendee.meeting_id == meeting_id
                )
                att_result = await session.execute(att_stmt)
                attendees = att_result.all()

                person_ids: list[tuple[str, str]] = []
                for att_name, att_email in attendees:
                    person_id = att_email or att_name.lower().replace(" ", "_")
                    await neo4j_svc.create_entity("Person", person_id, {
                        "name": att_name,
                        "email": att_email,
                    })
                    await neo4j_svc.create_relationship(
                        "Person", person_id,
                        "Meeting", str(meeting_id),
                        "ATTENDED",
                        {"role": "attendee"},
                    )
                    person_ids.append((person_id, att_name))
                    new_rels += 1

                for (p1_id, p1_name), (p2_id, p2_name) in combinations(person_ids, 2):
                    if p1_id == p2_id:
                        continue
                    result_rel = await neo4j_svc.strengthen_relationship(
                        "Person", p1_id,
                        "Person", p2_id,
                        "KNOWS",
                        context=f"Co-attended: {title}",
                        last_seen=str(meeting_id),
                    )
                    if result_rel:
                        strength = result_rel.get("strength", 1)
                        if strength > 1:
                            strengthened += 1
                        else:
                            new_rels += 1

                meetings_processed += 1

            except Exception as e:
                logger.warning("Relationship build failed for meeting %s: %s", meeting_id, e)
                errors.append({"meeting_id": str(meeting_id), "error": str(e)})

    logger.info(
        "Relationships: %d meetings processed, %d new, %d strengthened, %d errors",
        meetings_processed, new_rels, strengthened, len(errors),
    )
    return {
        "meetings_processed": meetings_processed,
        "new_relationships": new_rels,
        "strengthened": strengthened,
        "errors": errors,
    }


class RelationshipBuilderAgent(BaseAgent):
    name = "relationship_builder"
    description = "Builds entity relationships in Neo4j from meeting co-occurrence"
    pipeline = "sync"
    dependencies = ["entity_extraction"]
    required_mcp_providers = []

    async def should_run(self, state: AgentState) -> bool:
        return (
            len(state.get("new_meeting_ids", [])) > 0
            or len(state.get("updated_meeting_ids", [])) > 0
            or len(state.get("resolved_entities", [])) > 0
        )

    async def process(self, state: AgentState) -> AgentState:
        result = await build_relationships_from_meetings()
        errors = list(state.get("errors", []))
        for e in result.get("errors", []):
            errors.append({"agent": self.name, **e})
        return {
            **state,
            "new_relationships": [{"count": result["new_relationships"]}],
            "updated_relationships": [{"count": result["strengthened"]}],
            "errors": errors,
        }
