import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.registry import AgentRegistry
from app.api.routes import (
    action_items,
    agents,
    briefings,
    calendar,
    connections,
    meetings,
    profiles,
    relationships,
    search,
    status,
)
from app.config import settings
from app.db.neo4j_driver import close_neo4j_driver, init_neo4j_constraints
from app.mcp.registry import MCPRegistry
from app.services.scheduler import SchedulerService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    mcp_registry = MCPRegistry()
    mcp_registry.auto_discover()
    app.state.mcp_registry = mcp_registry
    logger.info("MCP providers registered: %s", [p.name for p in mcp_registry.list_all()])

    agent_registry = AgentRegistry()
    agent_registry.auto_discover()
    app.state.agent_registry = agent_registry
    logger.info("Agents registered: %s", [a.name for a in agent_registry.list_all()])

    issues = agent_registry.validate()
    if issues:
        for issue in issues:
            logger.warning("Agent validation: %s", issue)

    await init_neo4j_constraints()

    # Restore saved connections from DB and auto-connect local providers
    from app.db.postgres import async_session_factory
    from app.services.connection_service import ConnectionService

    async with async_session_factory() as session:
        conn_service = ConnectionService(session, mcp_registry)
        await conn_service.restore_connections()
        await session.commit()

    # Auto-connect Granola composite provider (cache always, MCP if tokens restored)
    try:
        granola = mcp_registry.get("granola")
        from app.mcp.base import ProviderStatus
        status = await granola.health_check()
        if status != ProviderStatus.HEALTHY:
            connected = await granola.connect({})
            if connected:
                logger.info("Granola auto-connected (cache fallback ready)")

        # Pre-discover OAuth metadata so the auth URL is available immediately
        if hasattr(granola, "ensure_oauth_discovered"):
            try:
                await granola.ensure_oauth_discovered()
                logger.info("Granola OAuth discovery complete")
            except Exception as oauth_err:
                logger.info("Granola OAuth discovery deferred: %s", oauth_err)
    except (KeyError, Exception) as e:
        logger.info("Granola auto-connect skipped: %s", e)

    scheduler = SchedulerService(
        redis_client=app.state.redis,
        agent_registry=agent_registry,
        mcp_registry=mcp_registry,
    )
    app.state.scheduler = scheduler
    await scheduler.start()

    yield

    await scheduler.stop()
    await app.state.redis.close()
    await close_neo4j_driver()


app = FastAPI(
    title="Personal Meeting Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings.router, prefix="/api/meetings", tags=["meetings"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(relationships.router, prefix="/api/relationships", tags=["relationships"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(action_items.router, prefix="/api/action-items", tags=["action-items"])
app.include_router(briefings.router, prefix="/api/briefings", tags=["briefings"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(connections.router, prefix="/api/connections", tags=["connections"])
app.include_router(status.router, prefix="/api/status", tags=["status"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
