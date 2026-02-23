"""Seed script to create sample briefings for UI testing."""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.postgres import async_session_factory
from app.models.briefing import Briefing
from app.models.meeting import Meeting


SAMPLE_BRIEFINGS = [
    {
        "title": "Weekly Product Sync",
        "content": """## Overview
This is your weekly product sync with the engineering and design teams. Based on previous meetings, the main focus has been on the dashboard redesign and API v2 launch timeline.

## Attendees
- Sarah Chen (Engineering Lead) - You've had 12 meetings together. She typically drives technical discussions and sprint planning.
- Mike Johnson (Product Designer) - 8 meetings together. Recently presented the new dashboard mockups.
- Alex Rivera (Backend Engineer) - 5 meetings together. Working on API v2 endpoints.

## Discussion Points
- Review progress on dashboard redesign (Sprint 14 items)
- API v2 beta launch timeline - originally targeted for March 1st
- Address the performance regression reported in last week's standup
- Discuss user feedback from the beta testing group
- Plan for Q2 OKR alignment session

## Open Action Items
- [Sarah] Complete API v2 endpoint documentation (due Feb 25)
- [Mike] Finalize dashboard color palette based on accessibility audit
- [You] Review and approve the revised sprint backlog
- [Alex] Fix the N+1 query issue in the meetings endpoint

## Key Reminders
- Sarah mentioned she'll be OOO next week, so finalize any blocking decisions today
- The stakeholder demo is scheduled for March 5th""",
        "topics": [
            "Dashboard redesign progress review",
            "API v2 beta launch timeline",
            "Performance regression investigation",
            "User feedback from beta testing",
            "Q2 OKR alignment planning",
        ],
        "attendee_context": [
            "Sarah Chen: Engineering Lead, 12 previous meetings, drives technical discussions",
            "Mike Johnson: Product Designer, 8 previous meetings, working on dashboard redesign",
            "Alex Rivera: Backend Engineer, 5 previous meetings, API v2 development",
        ],
        "action_items_context": [
            "Sarah: Complete API v2 endpoint documentation (due Feb 25)",
            "Mike: Finalize dashboard color palette",
            "You: Review revised sprint backlog",
            "Alex: Fix N+1 query issue",
        ],
    },
    {
        "title": "1:1 with Manager - Quarterly Review",
        "content": """## Overview
Quarterly review meeting with your manager, David Park. This is a good opportunity to discuss career growth, project alignment, and any blockers.

## Attendees
- David Park (Engineering Manager) - Regular 1:1 cadence, 24 meetings together. Known focus areas: team velocity, individual growth plans.

## Discussion Points
- Review Q1 accomplishments and impact metrics
- Discuss the personal meeting assistant project and its potential as an internal tool
- Address the need for additional engineering resources for API v2
- Career growth conversation: Senior Engineer track milestones

## Open Action Items
- [You] Prepare Q1 impact summary document
- [David] Share updated promotion criteria framework

## Key Reminders
- David mentioned interest in the meeting assistant tool during the last all-hands
- Compensation review cycle starts next month""",
        "topics": [
            "Q1 accomplishments review",
            "Meeting assistant project discussion",
            "Engineering resource planning",
            "Career growth milestones",
        ],
        "attendee_context": [
            "David Park: Engineering Manager, 24 previous meetings, focuses on team velocity and growth",
        ],
        "action_items_context": [
            "You: Prepare Q1 impact summary document",
            "David: Share updated promotion criteria framework",
        ],
    },
]


async def main():
    async with async_session_factory() as session:
        stmt = select(Meeting).order_by(Meeting.date.desc()).limit(2)
        result = await session.execute(stmt)
        meetings = result.scalars().all()

        for i, sample in enumerate(SAMPLE_BRIEFINGS):
            meeting_id = meetings[i].id if i < len(meetings) else None
            briefing = Briefing(
                id=uuid.uuid4(),
                meeting_id=meeting_id,
                calendar_event_id=f"gcal-event-{i + 1}",
                title=sample["title"],
                content=sample["content"],
                topics=sample["topics"],
                attendee_context=sample["attendee_context"],
                action_items_context=sample["action_items_context"],
            )
            session.add(briefing)
            print(f"Created briefing: {briefing.title} (id={briefing.id})")

        await session.commit()
        print(f"\nSeeded {len(SAMPLE_BRIEFINGS)} briefings.")


if __name__ == "__main__":
    asyncio.run(main())
