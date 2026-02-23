from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.mcp.base import AuthType, BaseMCPProvider, ProviderStatus

logger = logging.getLogger(__name__)


class GCalProvider(BaseMCPProvider):
    """Google Calendar MCP provider.

    Connects to the gcal-mcp Docker service via HTTP.
    The gcal-mcp service handles its own OAuth with Google
    using credentials mounted into the container.
    """

    name = "gcal"
    description = "Google Calendar - upcoming events, scheduling, and availability"
    auth_type = AuthType.OAUTH2

    def __init__(self) -> None:
        self._base_url: str = settings.gcal_mcp_url
        self._connected = False
        self._tools_cache: list[dict[str, Any]] = []

    async def connect(self, credentials: dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    self._connected = True
                    logger.info("Google Calendar MCP connected at %s", self._base_url)
                    return True
        except httpx.ConnectError:
            logger.warning("Google Calendar MCP service not reachable at %s", self._base_url)
        except Exception:
            logger.exception("GCal connect failed")
        self._connected = False
        return False

    async def disconnect(self) -> bool:
        self._connected = False
        self._tools_cache = []
        return True

    async def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list-events",
                "description": "List calendar events within a date range",
                "schema": {
                    "type": "object",
                    "properties": {
                        "timeMin": {"type": "string", "description": "Start time (ISO 8601)"},
                        "timeMax": {"type": "string", "description": "End time (ISO 8601)"},
                        "maxResults": {"type": "integer", "default": 10},
                    },
                },
            },
            {
                "name": "get-event",
                "description": "Get details for a specific calendar event",
                "schema": {
                    "type": "object",
                    "properties": {"eventId": {"type": "string"}},
                    "required": ["eventId"],
                },
            },
            {
                "name": "search-events",
                "description": "Search calendar events by text query",
                "schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "get-freebusy",
                "description": "Check availability across calendars",
                "schema": {
                    "type": "object",
                    "properties": {
                        "timeMin": {"type": "string"},
                        "timeMax": {"type": "string"},
                    },
                    "required": ["timeMin", "timeMax"],
                },
            },
        ]

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        if not self._connected:
            raise RuntimeError("Google Calendar MCP provider not connected")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/tools/{tool_name}",
                    json=params,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception:
            logger.exception("GCal execute_tool(%s) failed", tool_name)
            raise

    async def health_check(self) -> ProviderStatus:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return ProviderStatus.HEALTHY
                return ProviderStatus.DEGRADED
        except httpx.ConnectError:
            return ProviderStatus.DISCONNECTED
        except Exception:
            return ProviderStatus.DEGRADED
