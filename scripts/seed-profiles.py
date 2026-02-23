"""Create profiles from existing meeting attendees."""

import asyncio
import uuid

from sqlalchemy import func, select

from app.db.postgres import async_session_factory
from app.models.meeting import Attendee
from app.models.profile import Profile


async def seed():
    async with async_session_factory() as session:
        result = await session.execute(
            select(Attendee.name, Attendee.email, Attendee.role)
            .distinct(Attendee.name)
        )
        attendees = result.all()

        created = 0
        for name, email, role in attendees:
            existing = await session.execute(
                select(Profile).where(func.lower(Profile.name) == name.lower())
            )
            if existing.scalar_one_or_none():
                continue

            profile = Profile(
                id=uuid.uuid4(),
                type="contact",
                name=name,
                email=email,
                bio=f"{role}" if role else None,
                traits={"observed_roles": [role] if role else [], "meeting_count": 1},
                learning_log=[],
            )
            session.add(profile)
            created += 1

        await session.commit()
        print(f"Created {created} profiles from attendees ({len(attendees)} unique attendees found)")


if __name__ == "__main__":
    asyncio.run(seed())
