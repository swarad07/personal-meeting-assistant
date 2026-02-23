from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AgentRegistry
from app.db.postgres import get_db_session
from app.mcp.registry import MCPRegistry
from app.services.connection_service import ConnectionService
from app.services.scheduler import SchedulerService


def get_mcp_registry(request: Request) -> MCPRegistry:
    return request.app.state.mcp_registry


def get_agent_registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry


def get_scheduler(request: Request) -> SchedulerService:
    return request.app.state.scheduler


async def get_connection_service(
    session: AsyncSession = Depends(get_db_session),
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
) -> AsyncGenerator[ConnectionService, None]:
    yield ConnectionService(session, mcp_registry)
