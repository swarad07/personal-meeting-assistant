"""Granola Composite Provider — tries official MCP API first, falls back to local cache.

This is the only auto-discovered Granola provider (name="granola").
It wraps GranolaMCPProvider and GranolaCacheProvider, attempting the MCP
API for every tool call and transparently falling back to the local cache
when MCP is unavailable or fails.
"""

from __future__ import annotations

import logging
from typing import Any

from app.mcp.base import AuthType, BaseMCPProvider, ProviderStatus
from app.mcp.providers.granola_cache import GranolaCacheProvider
from app.mcp.providers.granola_mcp import GranolaMCPProvider

logger = logging.getLogger(__name__)


class GranolaProvider(BaseMCPProvider):
    name = "granola"
    description = "Granola AI meeting notes — MCP API with local-cache fallback"
    auth_type = AuthType.OAUTH2

    def __init__(self) -> None:
        self._mcp = GranolaMCPProvider()
        self._cache = GranolaCacheProvider()
        self._last_source: str = "unknown"

    # ── Connection lifecycle ──────────────────────────────────────

    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Connect both sub-providers.

        The cache provider always attempts to connect (no credentials needed).
        The MCP provider only connects if an access_token is supplied.
        """
        cache_ok = await self._cache.connect({})
        if cache_ok:
            logger.info("Granola cache sub-provider connected")

        mcp_ok = False
        if credentials.get("access_token"):
            mcp_ok = await self._mcp.connect(credentials)
            if mcp_ok:
                logger.info("Granola MCP sub-provider connected")
            else:
                logger.warning("Granola MCP sub-provider failed to connect; cache is fallback")

        return cache_ok or mcp_ok

    async def disconnect(self) -> bool:
        await self._mcp.disconnect()
        await self._cache.disconnect()
        return True

    # ── OAuth2 delegation ─────────────────────────────────────────

    def get_auth_url(self, redirect_uri: str) -> str | None:
        return self._mcp.get_auth_url(redirect_uri)

    async def ensure_oauth_discovered(self) -> None:
        """Pre-discover OAuth metadata so get_auth_url works synchronously."""
        await self._mcp._discover_oauth()

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any] | None:
        return await self._mcp.exchange_code(code, redirect_uri)

    async def refresh_token(self, refresh_tok: str) -> dict[str, Any] | None:
        return await self._mcp.refresh_token(refresh_tok)

    # ── Tool interface ────────────────────────────────────────────

    async def list_tools(self) -> list[dict[str, Any]]:
        cache_tools = await self._cache.list_tools()

        if self._mcp.is_connected:
            try:
                mcp_tools = await self._mcp.list_tools()
                if mcp_tools:
                    return mcp_tools
            except Exception:
                logger.debug("MCP list_tools failed, using cache tool list")

        return cache_tools

    @property
    def last_source(self) -> str:
        """Which sub-provider handled the most recent execute_tool call: 'mcp' or 'cache'."""
        return self._last_source

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        if self._mcp.is_connected:
            try:
                result = await self._mcp.execute_tool(tool_name, params)
                self._last_source = "mcp"
                logger.debug("Granola MCP execute_tool(%s) succeeded", tool_name)
                return result
            except Exception as exc:
                logger.warning(
                    "Granola MCP execute_tool(%s) failed (%s), falling back to cache",
                    tool_name, exc,
                )

        if self._cache.is_connected:
            self._last_source = "cache"
            return await self._cache.execute_tool(tool_name, params)

        raise RuntimeError(
            "Granola provider: neither MCP nor cache sub-provider is connected"
        )

    async def health_check(self) -> ProviderStatus:
        if self._mcp.is_connected:
            try:
                mcp_status = await self._mcp.health_check()
                if mcp_status == ProviderStatus.HEALTHY:
                    return ProviderStatus.HEALTHY
            except Exception:
                pass

        if self._cache.is_connected:
            try:
                cache_status = await self._cache.health_check()
                if cache_status == ProviderStatus.HEALTHY:
                    return ProviderStatus.HEALTHY
                return ProviderStatus.DEGRADED
            except Exception:
                pass

        return ProviderStatus.DISCONNECTED

    @property
    def mcp_provider(self) -> GranolaMCPProvider:
        return self._mcp

    @property
    def cache_provider(self) -> GranolaCacheProvider:
        return self._cache
