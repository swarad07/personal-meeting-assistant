from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.models.action_item import ActionItem
from app.models.meeting import Meeting

router = APIRouter()


class ActionItemUpdate(BaseModel):
    status: str


@router.get("/")
async def list_action_items(
    status: str | None = Query(None, description="Filter by status: open, done, dismissed"),
    assignee: str | None = Query(None, description="Filter by assignee name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    base = select(ActionItem).join(Meeting)
    count_base = select(func.count()).select_from(ActionItem)

    if status:
        base = base.where(ActionItem.status == status)
        count_base = count_base.where(ActionItem.status == status)
    if assignee:
        base = base.where(ActionItem.assignee.ilike(f"%{assignee}%"))
        count_base = count_base.where(ActionItem.assignee.ilike(f"%{assignee}%"))

    total = (await session.execute(count_base)).scalar() or 0
    offset = (page - 1) * page_size

    stmt = base.order_by(ActionItem.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": str(ai.id),
                "meeting_id": str(ai.meeting_id),
                "assignee": ai.assignee,
                "description": ai.description,
                "status": ai.status,
                "due_date": ai.due_date.isoformat() if ai.due_date else None,
                "created_at": ai.created_at.isoformat(),
            }
            for ai in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{item_id}")
async def update_action_item(
    item_id: str,
    body: ActionItemUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    if body.status not in ("open", "done", "dismissed"):
        raise HTTPException(status_code=400, detail="Status must be: open, done, or dismissed")

    stmt = select(ActionItem).where(ActionItem.id == item_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    item.status = body.status
    await session.flush()

    return {
        "id": str(item.id),
        "status": item.status,
        "description": item.description,
    }
