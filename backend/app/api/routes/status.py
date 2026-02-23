from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_mcp_registry, get_scheduler
from app.db.postgres import get_db_session
from app.mcp.base import ProviderStatus
from app.mcp.registry import MCPRegistry
from app.models.agent_run_log import AgentRunLog
from app.services.scheduler import SchedulerService

router = APIRouter()

STALE_RUN_TIMEOUT_MINUTES = 10


@router.get("/")
async def get_system_status(
    request: Request,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    scheduler: SchedulerService = Depends(get_scheduler),
    session: AsyncSession = Depends(get_db_session),
):
    """Lightweight status endpoint for the status bar — single-call aggregate."""

    providers_status = []
    for provider in mcp_registry.list_all():
        try:
            health = await provider.health_check()
        except Exception:
            health = ProviderStatus.DISCONNECTED

        info = {
            "name": provider.name,
            "status": health.value,
            "auth_type": provider.auth_type.value,
        }

        if provider.name == "granola" and hasattr(provider, "mcp_provider"):
            info["source"] = (
                "mcp" if provider.mcp_provider.is_connected else "cache"
            )

        providers_status.append(info)

    # Recent agent runs (last 5 across all agents)
    runs_stmt = (
        select(AgentRunLog)
        .order_by(AgentRunLog.started_at.desc())
        .limit(5)
    )
    runs_result = await session.execute(runs_stmt)
    recent_runs = [
        {
            "id": str(r.id),
            "pipeline": r.pipeline,
            "agent_name": r.agent_name,
            "status": r.status,
            "started_at": r.started_at.isoformat() + "Z",
            "completed_at": r.completed_at.isoformat() + "Z" if r.completed_at else None,
            "duration_ms": r.duration_ms,
            "meetings_processed": r.meetings_processed,
            "errors_count": r.errors_count,
        }
        for r in runs_result.scalars().all()
    ]

    # Auto-fail runs stuck longer than the timeout
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_RUN_TIMEOUT_MINUTES)
    stale_update = (
        update(AgentRunLog)
        .where(AgentRunLog.status == "running", AgentRunLog.started_at < cutoff)
        .values(
            status="failed",
            completed_at=datetime.utcnow(),
            result_summary=f"Timed out after {STALE_RUN_TIMEOUT_MINUTES} minutes",
            errors_count=1,
        )
    )
    stale_result = await session.execute(stale_update)
    if stale_result.rowcount:
        await session.commit()

    # Currently running pipelines
    running_stmt = (
        select(AgentRunLog)
        .where(AgentRunLog.status == "running")
        .order_by(AgentRunLog.started_at.desc())
    )
    running_result = await session.execute(running_stmt)
    active_runs = []
    for r in running_result.scalars().all():
        elapsed_minutes = (datetime.utcnow() - r.started_at).total_seconds() / 60
        active_runs.append({
            "id": str(r.id),
            "pipeline": r.pipeline,
            "agent_name": r.agent_name,
            "started_at": r.started_at.isoformat() + "Z",
            "elapsed_minutes": round(elapsed_minutes, 1),
        })

    # Next scheduled run times
    next_sync = None
    next_briefing = None
    if scheduler._scheduler:
        for job in scheduler._scheduler.get_jobs():
            if job.id == "sync_pipeline" and job.next_run_time:
                next_sync = job.next_run_time.isoformat()
            elif job.id == "briefing_pipeline" and job.next_run_time:
                next_briefing = job.next_run_time.isoformat()

    return {
        "providers": providers_status,
        "active_runs": active_runs,
        "recent_runs": recent_runs,
        "scheduler": {
            "next_sync": next_sync,
            "next_briefing": next_briefing,
        },
        "stale_timeout_minutes": STALE_RUN_TIMEOUT_MINUTES,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/cancel-run/{run_id}")
async def cancel_run(
    run_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Mark a running agent run as cancelled/failed."""
    stmt = select(AgentRunLog).where(AgentRunLog.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "running":
        raise HTTPException(status_code=400, detail=f"Run is already {run.status}")

    run.status = "failed"
    run.completed_at = datetime.utcnow()
    run.result_summary = "Cancelled by user"
    run.errors_count = (run.errors_count or 0) + 1
    if run.started_at:
        run.duration_ms = int((datetime.utcnow() - run.started_at).total_seconds() * 1000)
    await session.commit()

    return {"status": "cancelled", "run_id": run_id}
