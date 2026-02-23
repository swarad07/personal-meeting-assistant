from fastapi import APIRouter, Depends, Query
from typing import Any

from app.db.neo4j_driver import get_neo4j_driver
from app.services.neo4j_service import Neo4jService

router = APIRouter()


@router.get("/")
async def get_graph(
    entity_id: str | None = Query(None, description="Center graph on a specific entity"),
    type: str | None = Query(None, description="Filter by node type: person, organization, topic"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get the relationship graph data for visualization."""
    driver = await get_neo4j_driver()
    service = Neo4jService(driver)

    if entity_id:
        data = await service.get_entity_connections(entity_id, depth=2)
    else:
        data = await service.get_graph_data(limit=limit, node_type=type)

    return data


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Entity name to search"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search entities by name in the knowledge graph."""
    driver = await get_neo4j_driver()
    service = Neo4jService(driver)
    return await service.search_entities_by_name(q, limit=limit)


@router.get("/{entity_id}")
async def get_entity_detail(entity_id: str):
    """Get an entity and its immediate neighbors."""
    driver = await get_neo4j_driver()
    service = Neo4jService(driver)
    return await service.get_entity_with_neighbors(entity_id)


@router.get("/{entity_id}/meetings")
async def get_entity_meetings(entity_id: str):
    """Get all meetings related to an entity."""
    driver = await get_neo4j_driver()
    service = Neo4jService(driver)
    meeting_ids = await service.find_meetings_for_entity(entity_id)
    return {"entity_id": entity_id, "meeting_ids": meeting_ids}
