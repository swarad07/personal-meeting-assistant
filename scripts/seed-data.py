"""Seed the database with sample meetings for development testing."""

import asyncio
import uuid
from datetime import datetime, timedelta

from app.db.postgres import async_session_factory
from app.models.action_item import ActionItem
from app.models.meeting import Attendee, Meeting, TranscriptChunk

SAMPLE_MEETINGS = [
    {
        "title": "Q1 Product Roadmap Planning",
        "days_ago": 14,
        "duration": 60,
        "raw_notes": (
            "Discussed Q1 priorities. Sarah presented the feature backlog. "
            "We agreed to focus on search improvements and the new dashboard. "
            "Mike raised concerns about API performance under load. "
            "Decision: prioritize search over dashboard for January."
        ),
        "enhanced_notes": (
            "## Q1 Product Roadmap\n\n"
            "### Key Decisions\n"
            "- Search improvements take priority over dashboard redesign\n"
            "- API performance audit before scaling\n\n"
            "### Next Steps\n"
            "- Sarah to create detailed search spec by Friday\n"
            "- Mike to run load tests on current API"
        ),
        "summary": "Planned Q1 roadmap focusing on search and performance. Sarah leads search spec, Mike handles load testing.",
        "attendees": [
            {"name": "Sarah Chen", "email": "sarah@company.com", "role": "Product Lead"},
            {"name": "Mike Johnson", "email": "mike@company.com", "role": "Engineering Lead"},
            {"name": "Lisa Park", "email": "lisa@company.com", "role": "Designer"},
        ],
        "action_items": [
            {"assignee": "Sarah Chen", "description": "Create detailed search improvements spec", "status": "open"},
            {"assignee": "Mike Johnson", "description": "Run load tests on current API endpoints", "status": "open"},
        ],
        "transcript_chunks": [
            {"speaker": "Sarah Chen", "content": "Let me walk through the feature backlog for Q1. We have about 15 items total, but I think we need to narrow it down to 3 or 4 major initiatives.", "start_time": 0.0, "end_time": 120.0},
            {"speaker": "Mike Johnson", "content": "Before we commit to new features, I want to flag that our API response times have been creeping up. We're seeing p95 latencies above 500ms on the search endpoint.", "start_time": 120.0, "end_time": 240.0},
            {"speaker": "Lisa Park", "content": "From a user perspective, search is the number one complaint. People can't find what they need. The dashboard redesign is more of a nice-to-have.", "start_time": 240.0, "end_time": 360.0},
        ],
    },
    {
        "title": "Weekly Engineering Standup",
        "days_ago": 7,
        "duration": 30,
        "raw_notes": (
            "Sprint review. Search indexing pipeline is 70% complete. "
            "Alex found a bug in the date parsing for recurring events. "
            "Team velocity is on track for the quarter."
        ),
        "enhanced_notes": None,
        "summary": "Sprint update: search indexing 70% done, date parsing bug found, velocity on track.",
        "attendees": [
            {"name": "Mike Johnson", "email": "mike@company.com", "role": "Engineering Lead"},
            {"name": "Alex Rivera", "email": "alex@company.com", "role": "Backend Engineer"},
            {"name": "Jordan Lee", "email": "jordan@company.com", "role": "Frontend Engineer"},
        ],
        "action_items": [
            {"assignee": "Alex Rivera", "description": "Fix date parsing bug for recurring events", "status": "done"},
            {"assignee": "Jordan Lee", "description": "Update search UI to show result highlights", "status": "open"},
        ],
        "transcript_chunks": [],
    },
    {
        "title": "Customer Feedback Review - Acme Corp",
        "days_ago": 3,
        "duration": 45,
        "raw_notes": (
            "Reviewed feedback from Acme Corp onboarding. They love the meeting notes feature "
            "but find the search confusing. Their CTO, David Kim, specifically asked about API access. "
            "We should schedule a follow-up demo of the new search when it's ready."
        ),
        "enhanced_notes": (
            "## Acme Corp Feedback\n\n"
            "### Positive\n- Meeting notes feature well received\n\n"
            "### Issues\n- Search UX confusing for new users\n- API access requested by CTO\n\n"
            "### Follow-up\n- Demo new search to David Kim once ready"
        ),
        "summary": "Acme Corp likes notes, finds search confusing. CTO David Kim wants API access. Follow-up demo planned.",
        "attendees": [
            {"name": "Sarah Chen", "email": "sarah@company.com", "role": "Product Lead"},
            {"name": "David Kim", "email": "david@acme.com", "role": "CTO (Acme Corp)"},
        ],
        "action_items": [
            {"assignee": "Sarah Chen", "description": "Schedule follow-up search demo with David Kim from Acme", "status": "open"},
        ],
        "transcript_chunks": [
            {"speaker": "David Kim", "content": "We've been using the meeting notes feature for about three weeks now and the team really likes it. The automatic summarization saves us probably 30 minutes per meeting.", "start_time": 0.0, "end_time": 120.0},
            {"speaker": "Sarah Chen", "content": "That's great to hear. What about the search functionality? We've been working on improvements.", "start_time": 120.0, "end_time": 180.0},
            {"speaker": "David Kim", "content": "Honestly, the search is a bit confusing. When I search for a person's name, I expect to see all meetings with them, but the results seem random. Also, is there an API we can use to pull data into our internal tools?", "start_time": 180.0, "end_time": 300.0},
        ],
    },
    {
        "title": "Pricing Strategy Discussion",
        "days_ago": 1,
        "duration": 50,
        "raw_notes": (
            "Discussed moving to a tiered pricing model. Current flat rate isn't sustainable. "
            "Sarah proposed three tiers: Starter, Pro, Enterprise. "
            "Mike flagged that Enterprise needs SSO and audit logging. "
            "We need to present this to the board next week."
        ),
        "enhanced_notes": None,
        "summary": "Planning tiered pricing (Starter/Pro/Enterprise). Enterprise needs SSO and audit. Board presentation next week.",
        "attendees": [
            {"name": "Sarah Chen", "email": "sarah@company.com", "role": "Product Lead"},
            {"name": "Mike Johnson", "email": "mike@company.com", "role": "Engineering Lead"},
        ],
        "action_items": [
            {"assignee": "Sarah Chen", "description": "Prepare pricing tier comparison for board presentation", "status": "open"},
            {"assignee": "Mike Johnson", "description": "Estimate engineering effort for SSO and audit logging", "status": "open"},
        ],
        "transcript_chunks": [],
    },
]


async def seed():
    async with async_session_factory() as session:
        for data in SAMPLE_MEETINGS:
            meeting_id = uuid.uuid4()
            meeting = Meeting(
                id=meeting_id,
                granola_id=f"seed-{meeting_id}",
                title=data["title"],
                date=datetime.utcnow() - timedelta(days=data["days_ago"]),
                duration=data["duration"],
                raw_notes=data["raw_notes"],
                enhanced_notes=data["enhanced_notes"],
                summary=data["summary"],
                synced_at=datetime.utcnow(),
            )
            session.add(meeting)

            for att in data["attendees"]:
                session.add(Attendee(meeting_id=meeting_id, **att))

            for ai in data["action_items"]:
                session.add(ActionItem(meeting_id=meeting_id, **ai))

            for i, chunk in enumerate(data["transcript_chunks"]):
                session.add(
                    TranscriptChunk(meeting_id=meeting_id, chunk_index=i, **chunk)
                )

        await session.commit()
        print(f"Seeded {len(SAMPLE_MEETINGS)} meetings with attendees, action items, and transcript chunks.")


if __name__ == "__main__":
    asyncio.run(seed())
