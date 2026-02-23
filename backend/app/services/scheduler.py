"""SchedulerService: Periodic pipeline execution with APScheduler + Redis distributed locking.

Runs two scheduled jobs:
- sync_pipeline: Fetches new meetings from Granola, extracts entities, builds relationships,
  updates profiles. Default interval: every 15 minutes.
- briefing_pipeline: Fetches upcoming calendar events and generates pre-meeting briefings.
  Default interval: every 30 minutes.

Redis SET NX is used as a distributed lock to prevent concurrent pipeline execution
across multiple backend instances.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AgentRegistry
from app.config import settings
from app.db.neo4j_driver import get_neo4j_driver
from app.db.postgres import async_session_factory
from app.mcp.registry import MCPRegistry
from app.models.agent_run_log import AgentRunLog

logger = logging.getLogger(__name__)

SYNC_LOCK_KEY = "meeting_assistant:sync_lock"
BRIEFING_LOCK_KEY = "meeting_assistant:briefing_lock"
DEFAULT_LOCK_TTL = 300


class SchedulerService:
    def __init__(
        self,
        redis_client: Redis,
        agent_registry: AgentRegistry,
        mcp_registry: MCPRegistry,
    ) -> None:
        self.redis_client = redis_client
        self.agent_registry = agent_registry
        self.mcp_registry = mcp_registry
        self._scheduler: AsyncIOScheduler | None = None

    async def start(self) -> None:
        self._scheduler = AsyncIOScheduler()

        self._scheduler.add_job(
            self._run_sync_pipeline,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="sync_pipeline",
            name="Meeting Sync Pipeline",
            max_instances=1,
        )

        self._scheduler.add_job(
            self._run_briefing_pipeline,
            "interval",
            minutes=settings.sync_interval_minutes * 2,
            id="briefing_pipeline",
            name="Briefing Generation Pipeline",
            max_instances=1,
        )

        self._scheduler.start()
        logger.info(
            "Scheduler started: sync every %d min, briefings every %d min",
            settings.sync_interval_minutes,
            settings.sync_interval_minutes * 2,
        )

    async def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Scheduler stopped")

    async def acquire_sync_lock(self, lock_key: str = SYNC_LOCK_KEY, ttl_seconds: int = DEFAULT_LOCK_TTL) -> bool:
        acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=ttl_seconds)
        return bool(acquired)

    async def release_sync_lock(self, lock_key: str = SYNC_LOCK_KEY) -> None:
        await self.redis_client.delete(lock_key)

    async def _run_sync_pipeline(self) -> None:
        if not await self.acquire_sync_lock(SYNC_LOCK_KEY):
            logger.info("Sync pipeline already running (lock held), skipping")
            return

        try:
            await self._execute_pipeline("sync", "scheduled")
        finally:
            await self.release_sync_lock(SYNC_LOCK_KEY)

    async def _run_briefing_pipeline(self) -> None:
        if not await self.acquire_sync_lock(BRIEFING_LOCK_KEY):
            logger.info("Briefing pipeline already running (lock held), skipping")
            return

        try:
            await self._execute_pipeline("briefing", "scheduled")
        finally:
            await self.release_sync_lock(BRIEFING_LOCK_KEY)

    async def _execute_pipeline(self, pipeline: str, trigger: str) -> dict[str, Any]:
        """Run all agents in *pipeline* sequentially, creating per-agent run logs."""
        from app.agents.run_tracker import run_agent_with_logging

        start_time = time.monotonic()
        logger.info("Starting %s pipeline (trigger=%s)", pipeline, trigger)

        if pipeline == "sync":
            return await self._run_sync_agents(trigger)
        elif pipeline == "briefing":
            return await self._run_briefing_agents(trigger)
        else:
            return {"status": "skipped", "reason": f"Unknown pipeline: {pipeline}"}

    async def _run_sync_agents(self, trigger: str) -> dict[str, Any]:
        from app.agents.meeting_sync import sync_all_meetings
        from app.agents.profile_builder import build_profiles_from_meetings
        from app.agents.relationship_builder import build_relationships_from_meetings
        from app.agents.entity_extraction import extract_entities_for_meetings
        from app.agents.run_tracker import run_agent_with_logging
        from app.mcp.base import ProviderStatus

        errors: list[Any] = []
        sync_result = None

        try:
            granola = self.mcp_registry.get("granola")
            if (await granola.health_check()) == ProviderStatus.HEALTHY:
                sync_result = await run_agent_with_logging(
                    "meeting_sync", "sync", trigger, sync_all_meetings,
                    fn_args=(granola,),
                )
                errors.extend(sync_result.get("errors", []))
        except (KeyError, Exception) as e:
            logger.warning("Sync step skipped: %s", e)

        try:
            profile_result = await run_agent_with_logging(
                "profile_builder", "sync", trigger, build_profiles_from_meetings,
            )
            errors.extend(profile_result.get("errors", []))
        except Exception as e:
            logger.warning("Profile builder failed: %s", e)

        try:
            await run_agent_with_logging(
                "relationship_builder", "sync", trigger, build_relationships_from_meetings,
            )
        except Exception as e:
            logger.warning("Relationship builder failed: %s", e)

        try:
            await run_agent_with_logging(
                "entity_extraction", "sync", trigger, extract_entities_for_meetings,
                fn_kwargs={
                    "meeting_ids": sync_result.get("new_meeting_ids", []) if sync_result else None,
                    "limit": 20,
                },
            )
        except Exception as e:
            logger.warning("Entity extraction failed: %s", e)

        return {"status": "completed", "errors": errors}

    async def _run_briefing_agents(self, trigger: str) -> dict[str, Any]:
        from app.agents.run_tracker import run_agent_with_logging

        try:
            from app.agents.briefing_generator import generate_briefings_for_upcoming
            await run_agent_with_logging(
                "briefing_generator", "briefing", trigger, generate_briefings_for_upcoming,
            )
        except Exception as e:
            logger.warning("Briefing generator failed: %s", e)

        return {"status": "completed", "errors": []}

    async def trigger_pipeline(self, pipeline: str, trigger: str = "manual") -> dict[str, Any]:
        lock_key = SYNC_LOCK_KEY if pipeline == "sync" else BRIEFING_LOCK_KEY
        if not await self.acquire_sync_lock(lock_key, ttl_seconds=600):
            return {"status": "skipped", "reason": "Pipeline already running"}

        try:
            return await self._execute_pipeline(pipeline, trigger)
        finally:
            await self.release_sync_lock(lock_key)
