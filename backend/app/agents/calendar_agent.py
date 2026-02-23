"""CalendarAgent: Fetches upcoming calendar events and enriches with known entity data.

First agent in the briefing pipeline. It:
1. Queries Google Calendar MCP for upcoming events (next 24-48 hours)
2. Matches attendee emails to known profiles/entities
3. Enriches event data with relationship context
4. Populates upcoming_meetings in state for BriefingGeneratorAgent
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentState, BaseAgent
from app.mcp.base import ProviderStatus
from app.models.profile import Profile

logger = logging.getLogger(__name__)


class CalendarAgent(BaseAgent):
    name = "calendar_agent"
    description = "Fetches upcoming calendar events and enriches with known attendee context"
    pipeline = "briefing"
    dependencies = []
    required_mcp_providers = ["gcal"]

    async def should_run(self, state: AgentState) -> bool:
        mcp_registry = state.get("mcp_registry")
        if not mcp_registry:
            return False
        try:
            provider = mcp_registry.get("gcal")
            status = await provider.health_check()
            return status == ProviderStatus.HEALTHY
        except (KeyError, Exception):
            logger.info("GCal MCP not available, calendar agent will not run")
            return False

    async def process(self, state: AgentState) -> AgentState:
        mcp_registry = state["mcp_registry"]
        db_session: AsyncSession = state["db_session"]
        errors: list[dict[str, Any]] = list(state.get("errors", []))

        gcal = mcp_registry.get("gcal")

        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(hours=48)).isoformat() + "Z"

        try:
            raw_events = await gcal.execute_tool("list-events", {
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": 20,
            })
        except Exception as e:
            logger.exception("Failed to fetch calendar events")
            errors.append({"agent": self.name, "error": f"GCal fetch failed: {e}"})
            return {**state, "upcoming_meetings": [], "errors": errors}

        events = self._parse_events(raw_events)
        logger.info("Fetched %d upcoming calendar events", len(events))

        enriched = []
        for event in events:
            try:
                enriched_event = await self._enrich_event(db_session, event)
                enriched.append(enriched_event)
            except Exception as e:
                logger.warning("Failed to enrich event %s: %s", event.get("title"), e)
                enriched.append(event)

        return {
            **state,
            "upcoming_meetings": enriched,
            "errors": errors,
        }

    def _parse_events(self, raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return [self._normalize_event(e) for e in raw if isinstance(e, dict)]
        if isinstance(raw, dict):
            items = raw.get("items", raw.get("events", []))
            return [self._normalize_event(e) for e in items if isinstance(e, dict)]
        return []

    def _normalize_event(self, event: dict) -> dict[str, Any]:
        attendees = []
        for att in event.get("attendees", []):
            if isinstance(att, str):
                attendees.append({"email": att})
            elif isinstance(att, dict):
                attendees.append({
                    "email": att.get("email"),
                    "name": att.get("displayName", att.get("name")),
                    "response_status": att.get("responseStatus"),
                })

        start = event.get("start", {})
        end = event.get("end", {})

        return {
            "event_id": event.get("id"),
            "title": event.get("summary", event.get("title", "Untitled")),
            "start": start.get("dateTime", start) if isinstance(start, dict) else start,
            "end": end.get("dateTime", end) if isinstance(end, dict) else end,
            "description": event.get("description"),
            "location": event.get("location"),
            "attendees": attendees,
            "known_attendees": [],
        }

    async def _enrich_event(
        self, session: AsyncSession, event: dict[str, Any]
    ) -> dict[str, Any]:
        known = []
        for att in event.get("attendees", []):
            email = att.get("email")
            if not email:
                continue

            stmt = select(Profile).where(
                func.lower(Profile.email) == email.lower()
            )
            result = await session.execute(stmt)
            profile = result.scalar_one_or_none()

            if profile:
                known.append({
                    "profile_id": str(profile.id),
                    "name": profile.name,
                    "email": profile.email,
                    "bio": profile.bio,
                    "meeting_count": (profile.traits or {}).get("meeting_count", 0),
                })

        event["known_attendees"] = known
        return event
