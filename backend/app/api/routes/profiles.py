from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.models.action_item import ActionItem
from app.models.meeting import Attendee, Meeting
from app.models.profile import Profile

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: str | None = None
    bio: str | None = None
    notes: str | None = None


@router.get("/")
async def list_profiles(
    type: str | None = Query(None, description="Filter by type: self, contact, org"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    base = select(Profile)
    count_base = select(func.count()).select_from(Profile)

    if type:
        base = base.where(Profile.type == type)
        count_base = count_base.where(Profile.type == type)

    total = (await session.execute(count_base)).scalar() or 0
    offset = (page - 1) * page_size

    stmt = base.order_by(Profile.name).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    profiles = result.scalars().all()

    items = []
    for p in profiles:
        meeting_count = await _get_meeting_count(session, p.name)
        items.append({
            "id": str(p.id),
            "type": p.type,
            "name": p.name,
            "email": p.email,
            "bio": p.bio,
            "traits": p.traits,
            "meeting_count": meeting_count,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/me")
async def get_own_profile(
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Profile).where(Profile.type == "self")
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        from app.agents.profile_builder import ProfileBuilderAgent
        import uuid
        profile = Profile(
            id=uuid.uuid4(),
            type="self",
            name="Me",
            bio="Your personal profile. Update your name and bio below.",
            traits={},
            learning_log=[],
        )
        session.add(profile)
        await session.flush()

    return await _profile_detail(session, profile)


@router.get("/{profile_id}")
async def get_profile(
    profile_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Profile).where(Profile.id == profile_id)
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return await _profile_detail(session, profile)


@router.patch("/me")
async def update_own_profile(
    body: ProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Profile).where(Profile.type == "self")
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Self profile not found")

    if body.name is not None:
        profile.name = body.name
    if body.bio is not None:
        profile.bio = body.bio
    if body.notes is not None:
        profile.notes = body.notes

    await session.flush()
    return await _profile_detail(session, profile)


@router.post("/{profile_id}/generate-bio")
async def generate_bio(
    profile_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Generate or regenerate an LLM bio for a single profile."""
    from app.agents.profile_builder import generate_bio_for_profile

    stmt = select(Profile).where(Profile.id == profile_id)
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        bio_result = await generate_bio_for_profile(profile_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return bio_result


@router.patch("/{profile_id}")
async def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Profile).where(Profile.id == profile_id)
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if body.name is not None:
        profile.name = body.name
    if body.bio is not None:
        profile.bio = body.bio
    if body.notes is not None:
        profile.notes = body.notes

    await session.flush()
    return await _profile_detail(session, profile)


async def _profile_detail(session: AsyncSession, profile: Profile) -> dict[str, Any]:
    meeting_count = await _get_meeting_count(session, profile.name)

    recent_stmt = (
        select(Meeting)
        .join(Attendee)
        .where(func.lower(Attendee.name) == profile.name.lower())
        .order_by(Meeting.date.desc())
        .limit(10)
    )
    meetings_result = await session.execute(recent_stmt)
    recent_meetings = [
        {
            "id": str(m.id),
            "title": m.title,
            "date": m.date.isoformat(),
            "summary": m.summary,
        }
        for m in meetings_result.scalars().all()
    ]

    action_stmt = (
        select(ActionItem)
        .where(
            func.lower(ActionItem.assignee) == profile.name.lower(),
            ActionItem.status == "open",
        )
        .order_by(ActionItem.created_at.desc())
        .limit(10)
    )
    ai_result = await session.execute(action_stmt)
    action_items = [
        {
            "id": str(ai.id),
            "description": ai.description,
            "status": ai.status,
            "meeting_id": str(ai.meeting_id),
        }
        for ai in ai_result.scalars().all()
    ]

    learning_log = profile.learning_log or []
    if not isinstance(learning_log, list):
        learning_log = []

    return {
        "id": str(profile.id),
        "type": profile.type,
        "name": profile.name,
        "email": profile.email,
        "bio": profile.bio,
        "notes": profile.notes,
        "traits": profile.traits,
        "learning_log": learning_log[-20:],
        "meeting_count": meeting_count,
        "recent_meetings": recent_meetings,
        "action_items": action_items,
    }


async def _get_meeting_count(session: AsyncSession, name: str) -> int:
    stmt = (
        select(func.count())
        .select_from(Attendee)
        .where(func.lower(Attendee.name) == name.lower())
    )
    return (await session.execute(stmt)).scalar() or 0
