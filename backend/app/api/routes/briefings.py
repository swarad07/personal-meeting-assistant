from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_scheduler
from app.db.postgres import get_db_session
from app.models.briefing import Briefing
from app.services.scheduler import SchedulerService

router = APIRouter()


@router.get("/")
async def list_briefings(
    page: int = 1,
    page_size: int = 10,
    session: AsyncSession = Depends(get_db_session),
):
    total_stmt = select(func.count()).select_from(Briefing)
    total = (await session.execute(total_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = (
        select(Briefing)
        .order_by(Briefing.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    briefings = result.scalars().all()

    return {
        "items": [_briefing_to_dict(b) for b in briefings],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{briefing_id}")
async def get_briefing(
    briefing_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Briefing).where(Briefing.id == briefing_id)
    result = await session.execute(stmt)
    briefing = result.scalar_one_or_none()
    if not briefing:
        raise HTTPException(status_code=404, detail="Briefing not found")

    return _briefing_to_dict(briefing)


@router.get("/event/{calendar_event_id}")
async def get_briefing_by_event(
    calendar_event_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Briefing)
        .where(Briefing.calendar_event_id == calendar_event_id)
        .order_by(Briefing.created_at.desc())
    )
    result = await session.execute(stmt)
    briefing = result.scalar_one_or_none()
    if not briefing:
        raise HTTPException(status_code=404, detail="No briefing found for this event")

    return _briefing_to_dict(briefing)


@router.post("/{briefing_id}/regenerate", status_code=202)
async def regenerate_briefing(
    briefing_id: str,
    scheduler: SchedulerService = Depends(get_scheduler),
):
    result = await scheduler.trigger_pipeline("briefing", trigger="manual")
    return {"message": "Briefing regeneration triggered", "result": result}


@router.post("/generate", status_code=202)
async def generate_briefings():
    """Generate briefings for upcoming meetings using standalone runner."""
    from app.agents.briefing_generator import generate_briefings_for_upcoming
    result = await generate_briefings_for_upcoming()
    return {"message": "Briefing generation complete", "result": result}


def _briefing_to_dict(b: Briefing) -> dict:
    return {
        "id": str(b.id),
        "meeting_id": str(b.meeting_id) if b.meeting_id else None,
        "calendar_event_id": b.calendar_event_id,
        "title": b.title,
        "content": b.content,
        "topics": b.topics,
        "attendee_context": b.attendee_context,
        "action_items_context": b.action_items_context,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }
