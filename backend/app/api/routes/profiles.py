from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.models.action_item import ActionItem
from app.models.meeting import Attendee, Meeting
from app.models.profile import Profile

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    bio: str | None = None
    notes: str | None = None


class AliasBody(BaseModel):
    email: str


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
        count_stmt = select(func.count()).select_from(Attendee).where(_attendee_filter(p))
        meeting_count = (await session.execute(count_stmt)).scalar() or 0
        items.append({
            "id": str(p.id),
            "type": p.type,
            "name": p.name,
            "email": p.email,
            "bio": p.bio,
            "traits": p.traits,
            "aliases": p.aliases,
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
    if body.email is not None:
        profile.email = body.email
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


@router.post("/{profile_id}/aliases")
async def add_alias(
    profile_id: str,
    body: AliasBody,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Profile).where(Profile.id == profile_id)
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    alias_email = body.email.strip().lower()
    if not alias_email:
        raise HTTPException(status_code=400, detail="Email cannot be empty")

    conflict = await session.execute(
        select(Profile).where(func.lower(Profile.email) == alias_email)
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="This email is already a primary email on another profile. Use merge instead.",
        )

    all_aliases = await session.execute(
        select(Profile).where(Profile.aliases.contains([alias_email]))
    )
    if all_aliases.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="This email is already an alias on another profile.",
        )

    if profile.email and profile.email.lower() == alias_email:
        raise HTTPException(status_code=409, detail="This is already the primary email.")

    aliases = list(profile.aliases or [])
    if alias_email in aliases:
        raise HTTPException(status_code=409, detail="This alias already exists.")

    aliases.append(alias_email)
    profile.aliases = aliases
    await session.flush()

    return await _profile_detail(session, profile)


@router.delete("/{profile_id}/aliases/{alias_email}")
async def remove_alias(
    profile_id: str,
    alias_email: str,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Profile).where(Profile.id == profile_id)
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    aliases = list(profile.aliases or [])
    normalized = alias_email.strip().lower()
    if normalized not in aliases:
        raise HTTPException(status_code=404, detail="Alias not found on this profile")

    aliases.remove(normalized)
    profile.aliases = aliases if aliases else None
    await session.flush()

    return await _profile_detail(session, profile)


@router.post("/{profile_id}/merge/{other_id}")
async def merge_profiles(
    profile_id: str,
    other_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Merge other_id profile into profile_id. The other profile is deleted."""
    if profile_id == other_id:
        raise HTTPException(status_code=400, detail="Cannot merge a profile with itself")

    primary = (await session.execute(
        select(Profile).where(Profile.id == profile_id)
    )).scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=404, detail="Primary profile not found")

    other = (await session.execute(
        select(Profile).where(Profile.id == other_id)
    )).scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="Profile to merge not found")

    aliases = list(primary.aliases or [])

    if other.email and other.email.lower() not in aliases:
        if not primary.email or primary.email.lower() != other.email.lower():
            aliases.append(other.email.lower())

    for a in (other.aliases or []):
        if a not in aliases and (not primary.email or primary.email.lower() != a):
            aliases.append(a)

    primary.aliases = aliases if aliases else None

    primary_traits = dict(primary.traits or {})
    other_traits = dict(other.traits or {})
    other_mc = other_traits.pop("meeting_count", 0) or 0
    primary_mc = primary_traits.get("meeting_count", 0) or 0
    primary_traits["meeting_count"] = primary_mc + other_mc
    for k, v in other_traits.items():
        if k not in primary_traits:
            primary_traits[k] = v
    primary.traits = primary_traits

    if not primary.bio and other.bio:
        primary.bio = other.bio

    primary_log = list(primary.learning_log or [])
    other_log = list(other.learning_log or [])
    primary_log.extend(other_log)
    primary.learning_log = primary_log if primary_log else None

    update_stmt = (
        Attendee.__table__.update()
        .where(func.lower(Attendee.name) == other.name.lower())
        .values(name=primary.name)
    )
    await session.execute(update_stmt)

    if other.email:
        update_email_stmt = (
            Attendee.__table__.update()
            .where(func.lower(Attendee.email) == other.email.lower())
            .values(name=primary.name)
        )
        await session.execute(update_email_stmt)

    await session.delete(other)
    await session.flush()

    return await _profile_detail(session, primary)


async def _profile_detail(session: AsyncSession, profile: Profile) -> dict[str, Any]:
    attendee_filter = _attendee_filter(profile)

    count_stmt = select(func.count()).select_from(Attendee).where(attendee_filter)
    meeting_count = (await session.execute(count_stmt)).scalar() or 0

    recent_stmt = (
        select(Meeting)
        .join(Attendee)
        .where(attendee_filter)
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
        "aliases": profile.aliases,
        "learning_log": learning_log[-20:],
        "meeting_count": meeting_count,
        "recent_meetings": recent_meetings,
        "action_items": action_items,
    }


def _attendee_filter(profile: Profile):
    """Build a SQLAlchemy where-clause matching attendees by email (preferred) or name."""
    if profile.email:
        return func.lower(Attendee.email) == profile.email.lower()
    return func.lower(Attendee.name) == profile.name.lower()
