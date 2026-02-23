"""Reusable run-tracking wrapper for agent executions.

Every agent invocation — whether triggered from the API, scheduler, or UI —
should go through run_agent_with_logging() so that AgentRunLog records are
created consistently.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable

from app.db.postgres import async_session_factory
from app.models.agent_run_log import AgentRunLog

logger = logging.getLogger(__name__)


async def run_agent_with_logging(
    agent_name: str,
    pipeline: str,
    trigger: str,
    execute_fn: Callable[..., Awaitable[dict[str, Any]]],
    *,
    fn_args: tuple = (),
    fn_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute *execute_fn* and wrap it with AgentRunLog lifecycle.

    Returns the dict produced by *execute_fn*, augmented with ``run_id``.
    """
    fn_kwargs = fn_kwargs or {}
    run_id = uuid.uuid4()
    start = time.monotonic()

    async with async_session_factory() as session:
        run_log = AgentRunLog(
            id=run_id,
            pipeline=pipeline,
            agent_name=agent_name,
            trigger=trigger,
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(run_log)
        await session.commit()

    try:
        result = await execute_fn(*fn_args, **fn_kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        error_count = len(result.get("errors", []))
        summary = _build_summary(agent_name, result)

        async with async_session_factory() as session:
            from sqlalchemy import select

            stmt = select(AgentRunLog).where(AgentRunLog.id == run_id)
            log = (await session.execute(stmt)).scalar_one()
            log.status = "failed" if error_count and not result.get("processed", result.get("new", 0)) else "completed"
            log.duration_ms = elapsed_ms
            log.completed_at = datetime.utcnow()
            log.errors_count = error_count
            log.result_summary = summary
            log.meetings_processed = (
                result.get("new", 0)
                + result.get("updated", 0)
                + result.get("meetings_processed", 0)
                + result.get("processed", 0)
            )
            log.entities_extracted = result.get("entities", 0)
            await session.commit()

        logger.info("%s completed in %dms: %s", agent_name, elapsed_ms, summary)
        return {**result, "run_id": str(run_id)}

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        async with async_session_factory() as session:
            from sqlalchemy import select

            stmt = select(AgentRunLog).where(AgentRunLog.id == run_id)
            log = (await session.execute(stmt)).scalar_one()
            log.status = "failed"
            log.duration_ms = elapsed_ms
            log.completed_at = datetime.utcnow()
            log.errors_count = 1
            log.result_summary = f"Error: {exc}"
            await session.commit()

        logger.exception("%s failed after %dms", agent_name, elapsed_ms)
        raise


def _build_summary(agent_name: str, result: dict[str, Any]) -> str:
    """Build a human-readable one-liner from the agent result dict."""
    parts: list[str] = []

    if "new" in result or "updated" in result:
        new = result.get("new", 0)
        updated = result.get("updated", 0)
        skipped = result.get("skipped", 0)
        if new:
            parts.append(f"{new} new")
        if updated:
            parts.append(f"{updated} updated")
        if skipped:
            parts.append(f"{skipped} skipped")

    if result.get("processed"):
        parts.append(f"{result['processed']} processed")
    if result.get("entities"):
        parts.append(f"{result['entities']} entities")
    if result.get("action_items"):
        parts.append(f"{result['action_items']} action items")
    if result.get("created"):
        parts.append(f"{result['created']} created")
    if result.get("meetings_processed"):
        parts.append(f"{result['meetings_processed']} meetings")
    if result.get("new_relationships"):
        parts.append(f"{result['new_relationships']} new relationships")
    if result.get("strengthened"):
        parts.append(f"{result['strengthened']} strengthened")
    if result.get("enriched"):
        parts.append(f"{result['enriched']} enriched")

    error_count = len(result.get("errors", []))
    if error_count:
        parts.append(f"{error_count} errors")

    if result.get("skipped_reason"):
        parts.append(result["skipped_reason"])

    return ", ".join(parts) if parts else "Completed"
