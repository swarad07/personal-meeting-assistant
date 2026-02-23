"""Granola Cache Provider — reads from the local Granola desktop cache file.

Granola stores all meeting data in a local JSON cache at:
  ~/Library/Application Support/Granola/cache-v3.json

This provider reads that file to supply meeting documents, transcripts,
attendees, and people data to the agent pipeline without any external API calls.

This is the fallback provider used when the official Granola MCP API is
unavailable or not authenticated.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.config import settings
from app.mcp.base import AuthType, BaseMCPProvider, ProviderStatus

logger = logging.getLogger(__name__)


class GranolaCacheProvider(BaseMCPProvider):
    # No class-level `name` — prevents auto-discovery by MCPRegistry.
    # This provider is instantiated by the composite GranolaProvider.
    name = ""
    description = "Granola AI meeting notes — local cache reader (fallback)"
    auth_type = AuthType.NONE

    def __init__(self) -> None:
        self._cache_path: Path | None = None
        self._connected = False
        self._cache: dict[str, Any] | None = None
        self._last_loaded: float = 0

    def _resolve_path(self) -> Path:
        raw = settings.granola_cache_path
        return Path(os.path.expanduser(raw))

    async def connect(self, credentials: dict[str, Any]) -> bool:
        path = self._resolve_path()
        if not path.exists():
            logger.warning("Granola cache not found at %s", path)
            return False

        try:
            self._load_cache(path)
            self._cache_path = path
            self._connected = True
            doc_count = len(self._state().get("documents", {}))
            logger.info("Granola cache connected: %d documents at %s", doc_count, path)
            return True
        except Exception:
            logger.exception("Failed to read Granola cache")
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        self._cache = None
        self._cache_path = None
        self._connected = False
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list-documents",
                "description": "List all meeting documents",
                "schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50},
                        "since": {"type": "string", "description": "ISO date — only docs created/updated after this"},
                    },
                },
            },
            {
                "name": "get-document",
                "description": "Get a specific meeting document by ID",
                "schema": {
                    "type": "object",
                    "properties": {"documentId": {"type": "string"}},
                    "required": ["documentId"],
                },
            },
            {
                "name": "get-transcript",
                "description": "Get transcript segments for a document",
                "schema": {
                    "type": "object",
                    "properties": {"documentId": {"type": "string"}},
                    "required": ["documentId"],
                },
            },
            {
                "name": "list-people",
                "description": "List all known people from Granola",
                "schema": {"type": "object", "properties": {}},
            },
        ]

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        if not self._connected:
            raise RuntimeError("Granola cache provider not connected")

        self._maybe_reload()

        if tool_name == "list-documents":
            return self._list_documents(
                limit=params.get("limit", 50),
                since=params.get("since"),
            )
        elif tool_name == "get-document":
            return self._get_document(params["documentId"])
        elif tool_name == "get-transcript":
            return self._get_transcript(params["documentId"])
        elif tool_name == "list-people":
            return self._list_people()
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def health_check(self) -> ProviderStatus:
        path = self._resolve_path()
        if not path.exists():
            return ProviderStatus.DISCONNECTED
        if not self._connected:
            return ProviderStatus.DISCONNECTED
        return ProviderStatus.HEALTHY

    def get_auth_url(self, redirect_uri: str) -> str | None:
        return None

    # ── Internal helpers ───────────────────────────────────────────

    def _load_cache(self, path: Path) -> None:
        with open(path, "r") as f:
            raw = json.load(f)
        cache_str = raw.get("cache", "{}")
        self._cache = json.loads(cache_str) if isinstance(cache_str, str) else cache_str
        self._last_loaded = os.path.getmtime(path)

    def _maybe_reload(self) -> None:
        if self._cache_path is None:
            return
        try:
            mtime = os.path.getmtime(self._cache_path)
            if mtime > self._last_loaded:
                logger.info("Granola cache updated, reloading")
                self._load_cache(self._cache_path)
        except OSError:
            pass

    def _state(self) -> dict[str, Any]:
        if self._cache is None:
            return {}
        return self._cache.get("state", {})

    def _list_documents(self, limit: int = 50, since: str | None = None) -> list[dict[str, Any]]:
        docs_dict = self._state().get("documents", {})
        results = []

        for doc_id, doc in docs_dict.items():
            if doc.get("deleted_at"):
                continue

            if since:
                updated = doc.get("updated_at") or doc.get("created_at", "")
                if updated < since:
                    continue

            results.append(self._normalize_document(doc))

        results.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return results[:limit]

    def _get_document(self, doc_id: str) -> dict[str, Any] | None:
        docs_dict = self._state().get("documents", {})
        doc = docs_dict.get(doc_id)
        if doc is None:
            return None
        return self._normalize_document(doc, include_notes=True)

    def _get_transcript(self, doc_id: str) -> list[dict[str, Any]]:
        transcripts = self._state().get("transcripts", {})
        segments = transcripts.get(doc_id, [])
        if not isinstance(segments, list):
            return []

        return [
            {
                "id": seg.get("id"),
                "start_timestamp": seg.get("start_timestamp"),
                "end_timestamp": seg.get("end_timestamp"),
                "text": seg.get("text", ""),
                "speaker_name": seg.get("speaker_name"),
                "speaker_identifier": seg.get("speaker_identifier"),
                "source": seg.get("source"),
            }
            for seg in segments
            if seg.get("text")
        ]

    def _list_people(self) -> list[dict[str, Any]]:
        people = self._state().get("people", [])
        if not isinstance(people, list):
            return []

        return [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "email": p.get("email"),
                "job_title": p.get("job_title"),
                "company_name": p.get("company_name"),
                "avatar": p.get("avatar"),
            }
            for p in people
            if p.get("name")
        ]

    def _prosemirror_to_markdown(self, node: dict[str, Any], depth: int = 0) -> str:
        """Convert a ProseMirror/TipTap document tree to Markdown text."""
        ntype = node.get("type", "")
        children = node.get("content", [])

        if ntype == "text":
            return node.get("text", "")

        if ntype == "doc":
            return "\n\n".join(
                self._prosemirror_to_markdown(c) for c in children
            ).strip()

        if ntype == "paragraph":
            return "".join(self._prosemirror_to_markdown(c) for c in children)

        if ntype == "heading":
            level = node.get("attrs", {}).get("level", 2)
            text = "".join(self._prosemirror_to_markdown(c) for c in children)
            return f"{'#' * level} {text}"

        if ntype == "bulletList":
            return "\n".join(
                self._prosemirror_to_markdown(c, depth) for c in children
            )

        if ntype == "listItem":
            prefix = "  " * depth + "- "
            inner = "".join(self._prosemirror_to_markdown(c, depth + 1) for c in children)
            return f"{prefix}{inner}"

        return "".join(self._prosemirror_to_markdown(c, depth) for c in children)

    def _normalize_document(self, doc: dict[str, Any], include_notes: bool = False) -> dict[str, Any]:
        people_data = doc.get("people", {})
        attendees = []
        if isinstance(people_data, dict):
            for att in people_data.get("attendees", []):
                attendees.append({
                    "email": att.get("email"),
                    "name": self._extract_person_name(att),
                    "company": att.get("details", {}).get("company", {}).get("name") if isinstance(att.get("details"), dict) else None,
                })

        gcal = doc.get("google_calendar_event") or {}
        start = gcal.get("start", {})
        end = gcal.get("end", {})

        result: dict[str, Any] = {
            "id": doc.get("id"),
            "title": doc.get("title", "Untitled"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
            "type": doc.get("type"),
            "summary": doc.get("summary"),
            "attendees": attendees,
            "gcal_event_id": gcal.get("id"),
            "start": start.get("dateTime") if isinstance(start, dict) else None,
            "end": end.get("dateTime") if isinstance(end, dict) else None,
            "transcribe": doc.get("transcribe", False),
            "valid_meeting": doc.get("valid_meeting", False),
        }

        if include_notes:
            notes_md = doc.get("notes_markdown", "")
            notes_plain = doc.get("notes_plain", "")

            if not notes_md and not notes_plain:
                structured = doc.get("notes")
                if isinstance(structured, dict) and structured.get("content"):
                    notes_md = self._prosemirror_to_markdown(structured)

            result["notes_markdown"] = notes_md
            result["notes_plain"] = notes_plain
            result["overview"] = doc.get("overview")

        return result

    def _extract_person_name(self, att: dict) -> str | None:
        details = att.get("details")
        if isinstance(details, dict):
            person = details.get("person", {})
            if isinstance(person, dict):
                name_obj = person.get("name", {})
                if isinstance(name_obj, dict):
                    return name_obj.get("fullName")
        return att.get("name")
