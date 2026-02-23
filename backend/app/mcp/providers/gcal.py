"""Google Calendar provider using direct OAuth2 + REST API.

No Docker sidecar required. Handles the full OAuth2 flow:
  get_auth_url -> exchange_code -> connect -> execute_tool (with auto-refresh)

Tokens are persisted via the ConnectionService (encrypted in DB).
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.mcp.base import AuthType, BaseMCPProvider, ProviderStatus

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPES = "https://www.googleapis.com/auth/calendar.readonly"


class GCalProvider(BaseMCPProvider):
    """Google Calendar provider — direct OAuth2 + Calendar REST API."""

    name = "gcal"
    description = "Google Calendar - upcoming events, scheduling, and availability"
    auth_type = AuthType.OAUTH2

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token_value: str | None = None
        self._connected = False

    # ── OAuth2 flow ───────────────────────────────────────────────

    def get_auth_url(self, redirect_uri: str) -> str | None:
        if not settings.google_client_id:
            logger.warning("GOOGLE_CLIENT_ID not configured")
            return None

        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": "gcal",
        }
        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        logger.info("Generated Google OAuth URL for redirect_uri=%s", redirect_uri)
        return url

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> dict[str, Any] | None:
        if not settings.google_client_id or not settings.google_client_secret:
            logger.error("Google OAuth credentials not configured")
            return None

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

        if resp.status_code != 200:
            logger.error(
                "Google token exchange failed: %d %s", resp.status_code, resp.text
            )
            return None

        tokens = resp.json()
        logger.info("Google token exchange successful")
        return tokens

    async def refresh_token(self, refresh_tok: str) -> dict[str, Any] | None:
        if not settings.google_client_id or not settings.google_client_secret:
            return None

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_tok,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "grant_type": "refresh_token",
                },
            )

        if resp.status_code != 200:
            logger.error(
                "Google token refresh failed: %d %s", resp.status_code, resp.text
            )
            return None

        data = resp.json()
        logger.info("Google access token refreshed")
        return data

    # ── Connection lifecycle ──────────────────────────────────────

    async def connect(self, credentials: dict[str, Any]) -> bool:
        access_token = credentials.get("access_token")
        refresh_tok = credentials.get("refresh_token")

        if not access_token:
            logger.warning("No access_token in credentials")
            return False

        self._access_token = access_token
        self._refresh_token_value = refresh_tok

        ok = await self._test_connection()
        if not ok and refresh_tok:
            refreshed = await self.refresh_token(refresh_tok)
            if refreshed:
                self._access_token = refreshed.get("access_token")
                ok = await self._test_connection()

        self._connected = ok
        if ok:
            logger.info("Google Calendar connected")
        else:
            logger.warning("Google Calendar connection verification failed")
        return ok

    async def disconnect(self) -> bool:
        self._access_token = None
        self._refresh_token_value = None
        self._connected = False
        return True

    async def health_check(self) -> ProviderStatus:
        if not self._connected or not self._access_token:
            return ProviderStatus.DISCONNECTED
        ok = await self._test_connection()
        if ok:
            return ProviderStatus.HEALTHY
        if self._refresh_token_value:
            refreshed = await self.refresh_token(self._refresh_token_value)
            if refreshed:
                self._access_token = refreshed.get("access_token")
                if await self._test_connection():
                    return ProviderStatus.HEALTHY
        return ProviderStatus.DEGRADED

    # ── Tools ─────────────────────────────────────────────────────

    async def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list-events",
                "description": "List calendar events within a date range",
                "schema": {
                    "type": "object",
                    "properties": {
                        "timeMin": {"type": "string", "description": "Start (ISO 8601)"},
                        "timeMax": {"type": "string", "description": "End (ISO 8601)"},
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
        if not self._connected or not self._access_token:
            raise RuntimeError("Google Calendar not connected")

        if tool_name == "list-events":
            return await self._list_events(params)
        elif tool_name == "get-event":
            return await self._get_event(params)
        elif tool_name == "search-events":
            return await self._search_events(params)
        elif tool_name == "get-freebusy":
            return await self._get_freebusy(params)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    # ── Google Calendar API calls ─────────────────────────────────

    async def _api_get(self, path: str, params: dict | None = None) -> dict:
        """GET request to Calendar API with automatic token refresh on 401."""
        url = f"{GOOGLE_CALENDAR_API}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params)

            if resp.status_code == 401 and self._refresh_token_value:
                refreshed = await self.refresh_token(self._refresh_token_value)
                if refreshed:
                    self._access_token = refreshed.get("access_token")
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    resp = await client.get(url, headers=headers, params=params)

            resp.raise_for_status()
            return resp.json()

    async def _api_post(self, path: str, json_body: dict) -> dict:
        """POST request to Calendar API with automatic token refresh on 401."""
        url = f"{GOOGLE_CALENDAR_API}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=json_body)

            if resp.status_code == 401 and self._refresh_token_value:
                refreshed = await self.refresh_token(self._refresh_token_value)
                if refreshed:
                    self._access_token = refreshed.get("access_token")
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    resp = await client.post(url, headers=headers, json=json_body)

            resp.raise_for_status()
            return resp.json()

    async def _list_events(self, params: dict[str, Any]) -> dict:
        query: dict[str, Any] = {
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if params.get("timeMin"):
            query["timeMin"] = params["timeMin"]
        if params.get("timeMax"):
            query["timeMax"] = params["timeMax"]
        if params.get("maxResults"):
            query["maxResults"] = str(params["maxResults"])

        return await self._api_get("/calendars/primary/events", query)

    async def _get_event(self, params: dict[str, Any]) -> dict:
        event_id = params["eventId"]
        return await self._api_get(f"/calendars/primary/events/{event_id}")

    async def _search_events(self, params: dict[str, Any]) -> dict:
        query: dict[str, Any] = {
            "q": params["query"],
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        return await self._api_get("/calendars/primary/events", query)

    async def _get_freebusy(self, params: dict[str, Any]) -> dict:
        body = {
            "timeMin": params["timeMin"],
            "timeMax": params["timeMax"],
            "items": [{"id": "primary"}],
        }
        return await self._api_post("/freeBusy/query", body)

    # ── Helpers ───────────────────────────────────────────────────

    async def _test_connection(self) -> bool:
        """Quick test: fetch 1 event to verify credentials work."""
        try:
            from datetime import datetime, timedelta

            now = datetime.utcnow()
            result = await self._api_get(
                "/calendars/primary/events",
                {
                    "maxResults": "1",
                    "timeMin": now.isoformat() + "Z",
                    "timeMax": (now + timedelta(days=1)).isoformat() + "Z",
                    "singleEvents": "true",
                },
            )
            return "items" in result or "kind" in result
        except Exception as e:
            logger.debug("GCal connection test failed: %s", e)
            return False
