from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.neo4j_driver import get_neo4j_driver
from app.db.postgres import get_db_session
from app.services.embedding_service import get_embedding_service
from app.services.search_service import SearchService

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 20


@router.post("/")
async def search(
    body: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    from app.db.neo4j_driver import _driver

    embedding_service = get_embedding_service()
    service = SearchService(session, _driver, embedding_service)

    results = await service.hybrid_search(
        query=body.query,
        page=body.page,
        page_size=body.page_size,
    )
    return results
