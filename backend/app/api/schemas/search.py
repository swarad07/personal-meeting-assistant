from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 20


class SearchResultItem(BaseModel):
    meeting_id: str
    title: str
    date: datetime
    relevance_score: float
    matched_excerpts: list[str] = []
    source: Literal["fts", "semantic", "graph"]


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int
    synthesis: str | None = None
