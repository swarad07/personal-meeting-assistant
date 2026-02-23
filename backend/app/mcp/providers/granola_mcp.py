"""Granola Official MCP Provider — connects to the Granola MCP API.

Uses OAuth 2.0 (Dynamic Client Registration + PKCE) and Streamable HTTP
Transport (JSON-RPC over HTTP POST) to interact with:
  https://mcp.granola.ai/mcp

Requires a Granola Business plan account for OAuth authentication.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from base64 import urlsafe_b64encode
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.mcp.base import AuthType, BaseMCPProvider, ProviderStatus

logger = logging.getLogger(__name__)

_JSONRPC_VERSION = "2.0"
_MCP_PROTOCOL_VERSION = "2025-03-26"
_REQUEST_TIMEOUT = 30.0


class GranolaMCPProvider(BaseMCPProvider):
    # Empty name prevents auto-discovery — instantiated by composite only
    name = ""
    description = "Granola AI meeting notes — official MCP API"
    auth_type = AuthType.OAUTH2

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token_value: str | None = None
        self._token_expires_at: float = 0
        self._connected = False
        self._request_counter = 0

        # OAuth metadata (populated on first auth request)
        self._authorization_endpoint: str | None = None
        self._token_endpoint: str | None = None
        self._registration_endpoint: str | None = None
        self._client_id: str | None = None

        # PKCE state (per-authorization-flow)
        self._code_verifier: str | None = None

        self._mcp_url = settings.granola_mcp_url
        self._base_url = self._mcp_url.rsplit("/", 1)[0]  # strip trailing /mcp

    # ── Connection lifecycle ──────────────────────────────────────

    async def connect(self, credentials: dict[str, Any]) -> bool:
        access_token = credentials.get("access_token")
        if not access_token:
            logger.warning("GranolaMCPProvider.connect called without access_token")
            return False

        self._access_token = access_token
        self._refresh_token_value = credentials.get("refresh_token")
        self._token_expires_at = credentials.get("expires_at", 0)
        self._client_id = credentials.get("client_id", self._client_id)

        try:
            await self._discover_oauth()
        except Exception:
            logger.warning("OAuth discovery failed during connect; will try initialize anyway")

        if self._token_expires_at and time.time() > self._token_expires_at - 60:
            if self._refresh_token_value:
                logger.info("Access token expired, attempting refresh before initialize")
                refreshed = await self.refresh_token(self._refresh_token_value)
                if not refreshed:
                    logger.warning("Token refresh failed during connect")
                    self._connected = False
                    return False
            else:
                logger.warning("Token expired and no refresh_token available")
                self._connected = False
                return False

        try:
            result = await self._jsonrpc_call("initialize", {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "personal-meeting-assistant", "version": "0.1.0"},
            })
            logger.info("Granola MCP connected: server=%s", result.get("serverInfo", {}))
            self._connected = True
            return True
        except Exception:
            logger.exception("Granola MCP connection verification failed")
            self._connected = False
            return False

    def get_current_tokens(self) -> dict[str, Any]:
        """Return the current token state for persistence after refresh."""
        tokens: dict[str, Any] = {}
        if self._access_token:
            tokens["access_token"] = self._access_token
        if self._refresh_token_value:
            tokens["refresh_token"] = self._refresh_token_value
        if self._token_expires_at:
            tokens["expires_at"] = self._token_expires_at
        if self._client_id:
            tokens["client_id"] = self._client_id
        return tokens

    async def disconnect(self) -> bool:
        self._access_token = None
        self._refresh_token_value = None
        self._token_expires_at = 0
        self._connected = False
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── OAuth2 flow ───────────────────────────────────────────────

    async def _discover_oauth(self) -> None:
        """Fetch OAuth authorization server metadata and perform DCR if needed."""
        if self._authorization_endpoint and self._token_endpoint:
            return

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            well_known_url = f"{self._base_url}/.well-known/oauth-authorization-server"
            resp = await client.get(well_known_url)
            resp.raise_for_status()
            meta = resp.json()

        self._authorization_endpoint = meta["authorization_endpoint"]
        self._token_endpoint = meta["token_endpoint"]
        self._registration_endpoint = meta.get("registration_endpoint")

        if self._registration_endpoint and not self._client_id:
            await self._dynamic_client_registration()

    async def _dynamic_client_registration(self) -> None:
        """Register as a public OAuth client via DCR."""
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self._registration_endpoint,  # type: ignore[arg-type]
                json={
                    "client_name": "Personal Meeting Assistant",
                    "redirect_uris": ["http://localhost:3000/settings/connections/callback"],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        self._client_id = data["client_id"]
        logger.info("Granola DCR complete, client_id=%s", self._client_id)

    def get_auth_url(self, redirect_uri: str) -> str | None:
        """Build the OAuth authorization URL with PKCE.

        Note: _discover_oauth must be called before this (async, so the
        composite provider does it).
        """
        if not self._authorization_endpoint or not self._client_id:
            return None

        self._code_verifier = secrets.token_urlsafe(64)
        code_challenge = urlsafe_b64encode(
            hashlib.sha256(self._code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "openid email profile offline_access",
            "state": "granola",
        }
        return f"{self._authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any] | None:
        if not self._token_endpoint or not self._client_id:
            logger.error("OAuth not discovered yet — cannot exchange code")
            return None

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "code_verifier": self._code_verifier or "",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._code_verifier = None

        expires_in = data.get("expires_in", 3600)
        result_tokens: dict[str, Any] = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at": time.time() + expires_in,
            "client_id": self._client_id,
        }

        id_token = data.get("id_token")
        if id_token:
            claims = self._decode_id_token(id_token)
            if claims.get("email"):
                result_tokens["user_email"] = claims["email"]
            if claims.get("name"):
                result_tokens["user_name"] = claims["name"]

        return result_tokens

    async def refresh_token(self, refresh_tok: str) -> dict[str, Any] | None:
        if not self._token_endpoint or not self._client_id:
            return None

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": self._client_id,
                },
            )
            if resp.status_code != 200:
                logger.warning("Granola token refresh failed: %s", resp.text)
                return None
            data = resp.json()

        expires_in = data.get("expires_in", 3600)
        new_tokens = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_tok),
            "expires_at": time.time() + expires_in,
            "client_id": self._client_id,
        }
        self._access_token = new_tokens["access_token"]
        self._refresh_token_value = new_tokens["refresh_token"]
        self._token_expires_at = new_tokens["expires_at"]
        return new_tokens

    # ── MCP tool interface ────────────────────────────────────────

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            result = await self._jsonrpc_call("tools/list", {})
            return result.get("tools", [])
        except Exception:
            logger.exception("Failed to list Granola MCP tools")
            return []

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        if not self._connected or not self._access_token:
            raise RuntimeError("Granola MCP provider not connected")

        await self._ensure_token_fresh()

        mcp_tool_name, mcp_params = self._map_tool(tool_name, params)
        result = await self._jsonrpc_call("tools/call", {
            "name": mcp_tool_name,
            "arguments": mcp_params,
        })
        return self._normalize_tool_result(tool_name, result)

    async def health_check(self) -> ProviderStatus:
        if not self._connected or not self._access_token:
            return ProviderStatus.DISCONNECTED
        try:
            await self._ensure_token_fresh()
            await self._jsonrpc_call("ping", {})
            return ProviderStatus.HEALTHY
        except Exception:
            return ProviderStatus.DEGRADED

    # ── JSON-RPC transport ────────────────────────────────────────

    async def _jsonrpc_call(self, method: str, params: dict[str, Any]) -> Any:
        self._request_counter += 1
        payload = {
            "jsonrpc": _JSONRPC_VERSION,
            "id": self._request_counter,
            "method": method,
            "params": params,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(self._mcp_url, json=payload, headers=headers)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return self._parse_sse_response(resp.text)

            data = resp.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Granola MCP error {err.get('code')}: {err.get('message')}")
        return data.get("result", data)

    @staticmethod
    def _parse_sse_response(body: str) -> Any:
        """Extract the last JSON-RPC result from a Server-Sent Events stream."""
        import json

        last_data: Any = None
        for line in body.splitlines():
            if line.startswith("data: "):
                try:
                    parsed = json.loads(line[6:])
                    if "result" in parsed:
                        last_data = parsed["result"]
                    elif "error" not in parsed:
                        last_data = parsed
                except json.JSONDecodeError:
                    continue
        if last_data is None:
            raise RuntimeError("No valid JSON-RPC result in SSE stream")
        return last_data

    async def _ensure_token_fresh(self) -> None:
        if self._token_expires_at and time.time() > self._token_expires_at - 60:
            if self._refresh_token_value:
                refreshed = await self.refresh_token(self._refresh_token_value)
                if not refreshed:
                    logger.warning("Token refresh failed; token may be expired")

    @staticmethod
    def _decode_id_token(token: str) -> dict[str, Any]:
        """Decode JWT id_token payload without signature verification."""
        import json
        from base64 import urlsafe_b64decode

        try:
            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            return json.loads(urlsafe_b64decode(payload_b64))
        except Exception:
            logger.debug("Failed to decode id_token")
            return {}

    # ── XML response parsing ─────────────────────────────────────

    def _parse_xml_response(self, internal_name: str, text: str) -> Any:
        """Parse Granola's XML-like MCP responses into normalized dicts."""
        import re

        if internal_name == "list-documents":
            meetings = []
            for m in re.finditer(r'<meeting\s+([^>]+?)(?:/\s*>|>(.*?)</meeting>)', text, re.DOTALL):
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
                body = m.group(2) or ""

                participants = []
                for p in re.finditer(r'<participant\s+([^>]*?)/?>', body):
                    p_attrs = dict(re.findall(r'(\w+)="([^"]*)"', p.group(1)))
                    participants.append({
                        "name": p_attrs.get("name"),
                        "email": p_attrs.get("email"),
                    })

                meetings.append({
                    "id": attrs.get("id"),
                    "title": attrs.get("title", "Untitled"),
                    "created_at": attrs.get("date") or attrs.get("created_at"),
                    "updated_at": attrs.get("updated_at"),
                    "start": attrs.get("date") or attrs.get("start"),
                    "end": attrs.get("end"),
                    "summary": attrs.get("summary"),
                    "attendees": participants,
                    "gcal_event_id": attrs.get("calendar_event_id"),
                    "transcribe": False,
                    "valid_meeting": True,
                })

            logger.info("Parsed %d meetings from XML response", len(meetings))
            return meetings

        if internal_name == "get-document":
            # get-document uses get_meetings with a filter, so the response
            # format is often the same as list-documents (an XML meetings list)
            meetings_from_xml = self._parse_xml_response("list-documents", text)
            if isinstance(meetings_from_xml, list) and len(meetings_from_xml) > 0:
                meeting = meetings_from_xml[0]
                # Enrich with notes from the body if available
                m_match = re.search(r'<meeting\s+[^>]*?>(.*?)</meeting>', text, re.DOTALL)
                if m_match:
                    body = m_match.group(1)
                    notes_match = re.search(r'<notes>(.*?)</notes>', body, re.DOTALL)
                    if notes_match:
                        meeting["notes_markdown"] = notes_match.group(1).strip()
                        meeting["notes_plain"] = meeting["notes_markdown"]
                    summary_match = re.search(r'<summary>(.*?)</summary>', body, re.DOTALL)
                    if summary_match:
                        meeting["summary"] = summary_match.group(1).strip()
                        meeting["overview"] = meeting["summary"]
                    elif not meeting.get("summary") and body.strip():
                        clean = re.sub(r'<[^>]+>', '', body).strip()
                        if clean:
                            meeting["notes_markdown"] = meeting.get("notes_markdown") or clean
                            meeting["notes_plain"] = meeting.get("notes_plain") or clean
                return meeting

            # Last resort: return the text as notes
            return {
                "notes_markdown": text,
                "notes_plain": text,
                "valid_meeting": True,
            }

        if internal_name == "get-transcript":
            segments = []
            # Try <segment> tags
            for i, seg in enumerate(re.finditer(r'<segment\s+([^>]*?)(?:/\s*>|>(.*?)</segment>)', text, re.DOTALL)):
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', seg.group(1)))
                seg_content = seg.group(2) or attrs.get("text", "")
                segments.append({
                    "id": attrs.get("id", str(i)),
                    "start_timestamp": attrs.get("start") or attrs.get("start_time"),
                    "end_timestamp": attrs.get("end") or attrs.get("end_time"),
                    "text": seg_content.strip(),
                    "speaker_name": attrs.get("speaker"),
                    "speaker_identifier": attrs.get("speaker_id"),
                    "source": "granola_mcp",
                })
            # Also try <utterance> or <line> tags (alternative format)
            if not segments:
                for i, seg in enumerate(re.finditer(r'<(?:utterance|line)\s+([^>]*?)(?:/\s*>|>(.*?)</(?:utterance|line)>)', text, re.DOTALL)):
                    attrs = dict(re.findall(r'(\w+)="([^"]*)"', seg.group(1)))
                    seg_content = seg.group(2) or attrs.get("text", "")
                    segments.append({
                        "id": str(i),
                        "start_timestamp": attrs.get("start") or attrs.get("timestamp"),
                        "end_timestamp": attrs.get("end"),
                        "text": seg_content.strip(),
                        "speaker_name": attrs.get("speaker") or attrs.get("name"),
                        "speaker_identifier": None,
                        "source": "granola_mcp",
                    })
            return segments

        return None

    # ── Tool mapping ──────────────────────────────────────────────

    @staticmethod
    def _map_tool(internal_name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map our internal tool names to Granola MCP tool names."""
        if internal_name == "list-documents":
            mcp_params: dict[str, Any] = {}
            if params.get("time_range"):
                mcp_params["time_range"] = params["time_range"]
            if params.get("custom_start"):
                mcp_params["custom_start"] = params["custom_start"]
            if params.get("custom_end"):
                mcp_params["custom_end"] = params["custom_end"]
            return ("list_meetings", mcp_params)

        if internal_name == "get-document":
            return ("get_meetings", {"meeting_ids": [params["documentId"]]})

        if internal_name == "get-transcript":
            return ("get_meeting_transcript", {"meeting_id": params["documentId"]})

        if internal_name == "list-people":
            return ("list_meetings", {})

        return (internal_name, params)

    def _normalize_tool_result(self, internal_name: str, result: Any) -> Any:
        """Normalize Granola MCP responses to match the format the sync agent expects."""
        import json as _json

        logger.debug("MCP raw result for %s: type=%s keys=%s",
                      internal_name, type(result).__name__,
                      list(result.keys()) if isinstance(result, dict) else "N/A")

        if not isinstance(result, dict):
            return self._apply_normalization(internal_name, result)

        content = result.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            first = content[0]
            if isinstance(first, dict) and first.get("type") == "text":
                text_content = first.get("text", "")

                # Detect MCP error responses returned as text content
                if text_content.startswith("MCP error"):
                    raise RuntimeError(f"Granola MCP tool error: {text_content[:200]}")

                # Try JSON first
                try:
                    parsed = _json.loads(text_content)
                    return self._apply_normalization(internal_name, parsed)
                except (_json.JSONDecodeError, KeyError):
                    pass

                # Granola MCP returns XML-like text — parse it
                if "<" in text_content:
                    parsed_xml = self._parse_xml_response(internal_name, text_content)
                    if parsed_xml is not None:
                        return parsed_xml

                # Plain text fallback — wrap as meeting detail if it looks like notes
                if internal_name == "get-document":
                    return {"notes_markdown": text_content, "notes_plain": text_content}
                return text_content

            return self._apply_normalization(internal_name, content)

        if "meetings" in result:
            return self._apply_normalization(internal_name, result["meetings"])

        return self._apply_normalization(internal_name, result)

    def _apply_normalization(self, internal_name: str, data: Any) -> Any:
        if internal_name == "list-documents":
            meetings = data
            if isinstance(data, dict):
                meetings = data.get("meetings", data.get("data", data.get("items", [])))
            if isinstance(meetings, list):
                normalized = [self._normalize_mcp_meeting(m) for m in meetings if isinstance(m, dict)]
                logger.debug("Normalized %d meetings from MCP (raw had %d items)",
                             len(normalized), len(meetings))
                return normalized
        if internal_name == "get-document":
            if isinstance(data, list) and len(data) > 0:
                return self._normalize_mcp_meeting(data[0], include_notes=True)
            if isinstance(data, dict):
                meeting = data.get("meeting", data)
                return self._normalize_mcp_meeting(meeting, include_notes=True)
        if internal_name == "get-transcript":
            transcript = data
            if isinstance(data, dict):
                transcript = data.get("transcript", data.get("segments", data.get("data", [])))
            if isinstance(transcript, list):
                return [self._normalize_mcp_transcript_segment(s) for s in transcript if isinstance(s, dict)]
        if internal_name == "list-people":
            return self._extract_people_from_meetings(data)
        return data

    @staticmethod
    def _normalize_mcp_meeting(m: dict[str, Any], include_notes: bool = False) -> dict[str, Any]:
        attendees = []
        for p in m.get("participants", m.get("attendees", [])):
            if isinstance(p, str):
                attendees.append({"email": None, "name": p, "company": None})
            elif isinstance(p, dict):
                attendees.append({
                    "email": p.get("email"),
                    "name": p.get("name") or p.get("displayName"),
                    "company": p.get("company"),
                })

        result: dict[str, Any] = {
            "id": m.get("id") or m.get("meetingId") or m.get("meeting_id"),
            "title": m.get("title", "Untitled"),
            "created_at": m.get("created_at") or m.get("createdAt"),
            "updated_at": m.get("updated_at") or m.get("updatedAt"),
            "type": m.get("type"),
            "summary": m.get("summary"),
            "attendees": attendees,
            "gcal_event_id": m.get("calendarEventId"),
            "start": m.get("start") or m.get("startTime"),
            "end": m.get("end") or m.get("endTime"),
            "transcribe": m.get("transcribe", False),
            "valid_meeting": True,
        }

        if include_notes:
            result["notes_markdown"] = m.get("notes_markdown") or m.get("notes", "")
            result["notes_plain"] = m.get("notes_plain", "")
            result["overview"] = m.get("overview") or m.get("summary")

        return result

    @staticmethod
    def _normalize_mcp_transcript_segment(seg: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": seg.get("id"),
            "start_timestamp": seg.get("start_timestamp") or seg.get("startTime"),
            "end_timestamp": seg.get("end_timestamp") or seg.get("endTime"),
            "text": seg.get("text", ""),
            "speaker_name": seg.get("speaker_name") or seg.get("speaker"),
            "speaker_identifier": seg.get("speaker_identifier"),
            "source": seg.get("source", "granola_mcp"),
        }

    @staticmethod
    def _extract_people_from_meetings(data: Any) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        meetings = data if isinstance(data, list) else []
        for m in meetings:
            for p in m.get("participants", m.get("attendees", [])):
                if isinstance(p, dict):
                    key = p.get("email") or p.get("name", "")
                    if key and key not in seen:
                        seen[key] = {
                            "id": p.get("id"),
                            "name": p.get("name") or p.get("displayName"),
                            "email": p.get("email"),
                            "job_title": p.get("job_title"),
                            "company_name": p.get("company"),
                            "avatar": p.get("avatar"),
                        }
        return list(seen.values())
