import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AgentRegistry
from app.api.dependencies import get_agent_registry
from app.db.postgres import get_db_session
from app.models.agent_run_log import AgentRunLog

router = APIRouter()

AGENT_EXECUTORS = {
    "meeting_sync": "_execute_meeting_sync",
    "entity_extraction": "_execute_entity_extraction",
    "profile_builder": "_execute_profile_builder",
    "relationship_builder": "_execute_relationship_builder",
    "briefing_generator": "_execute_briefing_generator",
    "calendar_agent": "_execute_calendar_agent",
}


def _serialize_run(r: AgentRunLog) -> dict:
    return {
        "id": str(r.id),
        "pipeline": r.pipeline,
        "agent_name": r.agent_name,
        "trigger": r.trigger,
        "status": r.status,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "duration_ms": r.duration_ms,
        "meetings_processed": r.meetings_processed,
        "entities_extracted": r.entities_extracted,
        "errors_count": r.errors_count,
        "tokens_used": r.tokens_used,
        "result_summary": r.result_summary,
    }


@router.get("/")
async def list_agents(
    registry: AgentRegistry = Depends(get_agent_registry),
    session: AsyncSession = Depends(get_db_session),
):
    """List all registered agents with their latest run status."""
    agents = registry.list_all()
    result = []
    for agent in agents:
        last_run_stmt = (
            select(AgentRunLog)
            .where(AgentRunLog.agent_name == agent.name)
            .order_by(AgentRunLog.started_at.desc())
            .limit(1)
        )
        last_run_result = await session.execute(last_run_stmt)
        last_run = last_run_result.scalar_one_or_none()

        total_runs_stmt = (
            select(func.count()).select_from(AgentRunLog).where(AgentRunLog.agent_name == agent.name)
        )
        total = (await session.execute(total_runs_stmt)).scalar() or 0

        success_stmt = (
            select(func.count())
            .select_from(AgentRunLog)
            .where(AgentRunLog.agent_name == agent.name, AgentRunLog.status == "completed")
        )
        successes = (await session.execute(success_stmt)).scalar() or 0

        result.append({
            "name": agent.name,
            "description": agent.description,
            "pipeline": agent.pipeline,
            "dependencies": agent.dependencies,
            "required_mcp_providers": agent.required_mcp_providers,
            "total_runs": total,
            "success_rate": round(successes / total, 2) if total > 0 else None,
            "can_trigger": agent.name in AGENT_EXECUTORS,
            "last_run": _serialize_run(last_run) if last_run else None,
        })
    return result


@router.get("/{agent_name}")
async def get_agent_detail(
    agent_name: str,
    registry: AgentRegistry = Depends(get_agent_registry),
    session: AsyncSession = Depends(get_db_session),
):
    """Get agent details and recent run history."""
    try:
        agent = registry.get(agent_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    total_runs_stmt = (
        select(func.count()).select_from(AgentRunLog).where(AgentRunLog.agent_name == agent_name)
    )
    total = (await session.execute(total_runs_stmt)).scalar() or 0

    success_stmt = (
        select(func.count())
        .select_from(AgentRunLog)
        .where(AgentRunLog.agent_name == agent_name, AgentRunLog.status == "completed")
    )
    successes = (await session.execute(success_stmt)).scalar() or 0

    runs_stmt = (
        select(AgentRunLog)
        .where(AgentRunLog.agent_name == agent_name)
        .order_by(AgentRunLog.started_at.desc())
        .limit(20)
    )
    runs_result = await session.execute(runs_stmt)
    runs = runs_result.scalars().all()

    return {
        "name": agent.name,
        "description": agent.description,
        "pipeline": agent.pipeline,
        "dependencies": agent.dependencies,
        "required_mcp_providers": agent.required_mcp_providers,
        "total_runs": total,
        "success_rate": round(successes / total, 2) if total > 0 else None,
        "can_trigger": agent.name in AGENT_EXECUTORS,
        "recent_runs": [_serialize_run(r) for r in runs],
    }


@router.post("/{agent_name}/trigger", status_code=202)
async def trigger_agent(agent_name: str, request: Request):
    """Trigger an individual agent run in the background."""
    if agent_name not in AGENT_EXECUTORS:
        raise HTTPException(status_code=400, detail=f"Agent '{agent_name}' cannot be triggered directly")

    executor_name = AGENT_EXECUTORS[agent_name]
    executor_fn = globals()[executor_name]

    mcp_registry = request.app.state.mcp_registry
    task = asyncio.create_task(executor_fn(mcp_registry))

    return {"message": f"Agent '{agent_name}' triggered", "agent_name": agent_name}


@router.get("/{agent_name}/runs")
async def list_agent_runs(
    agent_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """Get paginated run history for an agent."""
    offset = (page - 1) * page_size
    total_stmt = (
        select(func.count()).select_from(AgentRunLog).where(AgentRunLog.agent_name == agent_name)
    )
    total = (await session.execute(total_stmt)).scalar() or 0

    runs_stmt = (
        select(AgentRunLog)
        .where(AgentRunLog.agent_name == agent_name)
        .order_by(AgentRunLog.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    runs_result = await session.execute(runs_stmt)
    runs = runs_result.scalars().all()

    return {
        "items": [_serialize_run(r) for r in runs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{agent_name}/runs/{run_id}")
async def get_run_detail(
    agent_name: str,
    run_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get detailed information about a specific agent run."""
    stmt = select(AgentRunLog).where(
        AgentRunLog.id == run_id, AgentRunLog.agent_name == agent_name
    )
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return _serialize_run(run)


# ── Agent executor functions (background tasks) ────────────────────────────

async def _execute_meeting_sync(mcp_registry):
    from app.agents.meeting_sync import sync_all_meetings
    from app.agents.run_tracker import run_agent_with_logging
    from app.mcp.base import ProviderStatus

    try:
        granola = mcp_registry.get("granola")
        if (await granola.health_check()) != ProviderStatus.HEALTHY:
            return
    except KeyError:
        return

    await run_agent_with_logging(
        "meeting_sync", "sync", "manual", sync_all_meetings, fn_args=(granola,),
    )


async def _execute_entity_extraction(_mcp_registry):
    from app.agents.entity_extraction import extract_entities_for_meetings
    from app.agents.run_tracker import run_agent_with_logging

    await run_agent_with_logging(
        "entity_extraction", "sync", "manual", extract_entities_for_meetings,
        fn_kwargs={"limit": 20},
    )


async def _execute_profile_builder(_mcp_registry):
    from app.agents.profile_builder import build_profiles_from_meetings
    from app.agents.run_tracker import run_agent_with_logging

    await run_agent_with_logging(
        "profile_builder", "sync", "manual", build_profiles_from_meetings,
    )


async def _execute_relationship_builder(_mcp_registry):
    from app.agents.relationship_builder import build_relationships_from_meetings
    from app.agents.run_tracker import run_agent_with_logging

    await run_agent_with_logging(
        "relationship_builder", "sync", "manual", build_relationships_from_meetings,
    )


async def _execute_briefing_generator(_mcp_registry):
    from app.agents.briefing_generator import generate_briefings_for_upcoming
    from app.agents.run_tracker import run_agent_with_logging

    await run_agent_with_logging(
        "briefing_generator", "briefing", "manual", generate_briefings_for_upcoming,
    )


async def _execute_calendar_agent(mcp_registry):
    from app.agents.run_tracker import run_agent_with_logging

    async def _noop():
        return {"status": "no standalone function available"}

    await run_agent_with_logging(
        "calendar_agent", "briefing", "manual", _noop,
    )
