import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_scheduler
from app.db.postgres import get_db_session
from app.services.meeting_service import MeetingService
from app.services.scheduler import SchedulerService

router = APIRouter()


@router.get("/")
async def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    service = MeetingService(session)
    return await service.list_meetings(page=page, page_size=page_size)


@router.get("/{meeting_id}")
async def get_meeting(
    meeting_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    service = MeetingService(session)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.post("/{meeting_id}/resync")
async def resync_meeting(meeting_id: str, request: Request):
    """Re-fetch notes and transcript for a single meeting from Granola."""
    from app.agents.meeting_sync import resync_single_meeting

    mcp_registry = request.app.state.mcp_registry
    try:
        result = await resync_single_meeting(meeting_id, mcp_registry)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=503, detail="Granola provider not registered")

    return result


@router.post("/{meeting_id}/generate-brief")
async def generate_meeting_brief(meeting_id: str):
    """Generate a next-call brief for a completed meeting."""
    from app.agents.briefing_generator import generate_next_call_brief

    try:
        result = await generate_next_call_brief(meeting_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return result


@router.post("/{meeting_id}/generate-summary")
async def generate_meeting_summary(meeting_id: str):
    """Generate or regenerate an LLM summary for a single meeting."""
    from app.agents.entity_extraction import generate_summary_for_meeting

    try:
        result = await generate_summary_for_meeting(meeting_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return result


@router.post("/sync", status_code=202)
async def trigger_sync(request: Request):
    """Direct meeting sync from Granola — bypasses LangGraph for reliability."""
    from app.agents.meeting_sync import sync_all_meetings
    from app.agents.run_tracker import run_agent_with_logging
    from app.mcp.base import ProviderStatus

    mcp_registry = request.app.state.mcp_registry
    try:
        granola = mcp_registry.get("granola")
        status = await granola.health_check()
        if status != ProviderStatus.HEALTHY:
            raise HTTPException(status_code=503, detail="Granola provider not connected")
    except KeyError:
        raise HTTPException(status_code=503, detail="Granola provider not registered")

    result = await run_agent_with_logging(
        agent_name="meeting_sync",
        pipeline="sync",
        trigger="manual",
        execute_fn=sync_all_meetings,
        fn_args=(granola,),
    )

    return {
        "message": "Sync completed",
        "result": {
            "new": result["new"],
            "updated": result["updated"],
            "skipped": result["skipped"],
            "error_count": len(result["errors"]),
            "run_id": result.get("run_id"),
        },
    }


@router.post("/sync/full", status_code=202)
async def trigger_full_pipeline(request: Request):
    """Run the full sync pipeline: meetings -> profiles -> relationships -> entities."""
    from app.agents.meeting_sync import sync_all_meetings
    from app.agents.profile_builder import build_profiles_from_meetings
    from app.agents.relationship_builder import build_relationships_from_meetings
    from app.agents.entity_extraction import extract_entities_for_meetings
    from app.agents.run_tracker import run_agent_with_logging
    from app.mcp.base import ProviderStatus

    mcp_registry = request.app.state.mcp_registry
    results = {}

    sync_result = None
    try:
        granola = mcp_registry.get("granola")
        status = await granola.health_check()
        if status == ProviderStatus.HEALTHY:
            sync_result = await run_agent_with_logging(
                agent_name="meeting_sync",
                pipeline="sync",
                trigger="manual",
                execute_fn=sync_all_meetings,
                fn_args=(granola,),
            )
            results["sync"] = {
                "new": sync_result["new"],
                "updated": sync_result["updated"],
                "errors": len(sync_result["errors"]),
            }
        else:
            results["sync"] = {"skipped": "Granola not connected"}
    except KeyError:
        results["sync"] = {"skipped": "Granola not registered"}

    profile_result = await run_agent_with_logging(
        agent_name="profile_builder",
        pipeline="sync",
        trigger="manual",
        execute_fn=build_profiles_from_meetings,
    )
    results["profiles"] = {
        "created": profile_result["created"],
        "updated": profile_result["updated"],
        "errors": len(profile_result["errors"]),
    }

    rel_result = await run_agent_with_logging(
        agent_name="relationship_builder",
        pipeline="sync",
        trigger="manual",
        execute_fn=build_relationships_from_meetings,
    )
    results["relationships"] = {
        "meetings_processed": rel_result["meetings_processed"],
        "new": rel_result["new_relationships"],
        "strengthened": rel_result["strengthened"],
        "errors": len(rel_result["errors"]),
    }

    entity_result = await run_agent_with_logging(
        agent_name="entity_extraction",
        pipeline="sync",
        trigger="manual",
        execute_fn=extract_entities_for_meetings,
        fn_kwargs={
            "meeting_ids": sync_result.get("new_meeting_ids", []) if sync_result else None,
            "limit": 20,
        },
    )
    results["entity_extraction"] = {
        **{k: v for k, v in entity_result.items() if k not in ("errors", "run_id")},
        "errors": len(entity_result.get("errors", [])),
    }

    return {"message": "Full pipeline completed", "results": results}
