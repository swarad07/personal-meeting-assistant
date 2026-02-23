from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    NONE = "none"


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


class BaseMCPProvider(ABC):
    """Abstract base class for all MCP provider integrations.

    Subclasses are auto-discovered from the mcp/providers/ directory.
    """

    name: str = ""
    description: str = ""
    auth_type: AuthType = AuthType.NONE

    @abstractmethod
    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Establish connection using the provided credentials."""
        ...

    @abstractmethod
    async def disconnect(self) -> bool:
        """Clean up and close the connection."""
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of available MCP tools with their schemas."""
        ...

    @abstractmethod
    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Execute a named MCP tool with the given parameters."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """Return the current connection health status."""
        ...

    def get_auth_url(self, redirect_uri: str) -> str | None:
        """Return the OAuth authorization URL. Only applicable for OAuth2 providers."""
        return None

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any] | None:
        """Exchange an OAuth authorization code for tokens. Only for OAuth2 providers."""
        return None

    async def refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Refresh an expired OAuth token. Only for OAuth2 providers."""
        return None
