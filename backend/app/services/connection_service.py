from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.base import ProviderStatus
from app.mcp.registry import MCPRegistry
from app.models.app_setting import AppSetting
from app.models.connection import MCPConnection
from app.models.profile import Profile
from app.services.encryption_service import decrypt_tokens, encrypt_tokens

logger = logging.getLogger(__name__)


class ConnectionService:
    def __init__(self, session: AsyncSession, mcp_registry: MCPRegistry) -> None:
        self.session = session
        self.registry = mcp_registry

    async def list_connections(self) -> list[dict[str, Any]]:
        """List all registered providers with their connection status."""
        providers = self.registry.list_all()
        result = []
        for provider in providers:
            conn = await self._get_connection_record(provider.name)
            result.append({
                "provider": provider.name,
                "description": provider.description,
                "auth_type": provider.auth_type.value,
                "status": conn.status if conn else "disconnected",
                "last_sync": conn.last_sync.isoformat() if conn and conn.last_sync else None,
                "last_error": conn.last_error if conn else None,
            })
        return result

    async def get_auth_url(self, provider_name: str, redirect_uri: str) -> str | None:
        """Get the OAuth authorization URL for a provider."""
        provider = self.registry.get(provider_name)
        if hasattr(provider, "ensure_oauth_discovered"):
            await provider.ensure_oauth_discovered()
        return provider.get_auth_url(redirect_uri)

    async def handle_callback(
        self, provider_name: str, code: str, redirect_uri: str
    ) -> bool:
        """Exchange OAuth code for tokens and connect the provider."""
        provider = self.registry.get(provider_name)

        tokens = await provider.exchange_code(code, redirect_uri)
        if not tokens:
            tokens = {"access_token": code}

        connected = await provider.connect(tokens)

        conn = await self._get_or_create_connection(provider_name)
        if connected:
            conn.status = "connected"
            conn.oauth_tokens = encrypt_tokens(tokens)
            conn.last_error = None
        else:
            conn.status = "error"
            conn.last_error = "Connection failed after token exchange"

        await self.session.flush()

        if connected and provider_name == "granola":
            user_email = tokens.get("user_email")
            user_name = tokens.get("user_name")
            if user_email:
                await self._persist_primary_user(user_email, user_name)

        return connected

    async def connect_with_tokens(
        self, provider_name: str, tokens: dict[str, Any]
    ) -> bool:
        """Connect a provider directly with tokens (for API key auth or testing)."""
        provider = self.registry.get(provider_name)
        connected = await provider.connect(tokens)

        conn = await self._get_or_create_connection(provider_name)
        if connected:
            conn.status = "connected"
            conn.oauth_tokens = encrypt_tokens(tokens)
            conn.last_error = None
        else:
            conn.status = "error"
            conn.last_error = "Connection failed"

        await self.session.flush()
        return connected

    async def disconnect(self, provider_name: str) -> bool:
        """Disconnect a provider and clear stored tokens."""
        provider = self.registry.get(provider_name)
        await provider.disconnect()

        conn = await self._get_connection_record(provider_name)
        if conn:
            conn.status = "disconnected"
            conn.oauth_tokens = None
            conn.last_error = None
            await self.session.flush()

        return True

    async def check_health(self, provider_name: str) -> dict[str, Any]:
        """Check health of a specific provider."""
        provider = self.registry.get(provider_name)
        status = await provider.health_check()

        conn = await self._get_connection_record(provider_name)
        if conn:
            conn.status = "connected" if status == ProviderStatus.HEALTHY else status.value
            await self.session.flush()

        return {"provider": provider_name, "status": status.value}

    async def restore_connections(self) -> None:
        """Restore provider connections from stored tokens on startup."""
        from app.config import settings as app_cfg

        stmt = select(MCPConnection).where(MCPConnection.status == "connected")
        result = await self.session.execute(stmt)
        connections = result.scalars().all()

        for conn in connections:
            if not conn.oauth_tokens:
                continue
            try:
                tokens = decrypt_tokens(conn.oauth_tokens)
                provider = self.registry.get(conn.provider)
                connected = await provider.connect(tokens)
                if not connected:
                    conn.status = "error"
                    conn.last_error = "Failed to restore connection on startup"
                else:
                    # Persist refreshed tokens back to DB
                    mcp_sub = getattr(provider, "mcp_provider", None)
                    if mcp_sub and hasattr(mcp_sub, "get_current_tokens"):
                        fresh_tokens = mcp_sub.get_current_tokens()
                        if fresh_tokens.get("access_token"):
                            for key in ("user_email", "user_name"):
                                if key in tokens:
                                    fresh_tokens[key] = tokens[key]
                            conn.oauth_tokens = encrypt_tokens(fresh_tokens)
                            logger.info("Persisted refreshed tokens for %s", conn.provider)

                    if conn.provider == "granola" and not app_cfg.primary_user_email:
                        user_email = tokens.get("user_email")
                        user_name = tokens.get("user_name")
                        if user_email:
                            await self._persist_primary_user(user_email, user_name)
            except KeyError:
                logger.warning("Provider '%s' not registered, skipping restore", conn.provider)
            except Exception:
                logger.exception("Failed to restore connection for %s", conn.provider)
                conn.status = "error"
                conn.last_error = "Restore failed"

        await self.session.flush()

    async def update_last_sync(self, provider_name: str) -> None:
        conn = await self._get_connection_record(provider_name)
        if conn:
            conn.last_sync = datetime.now(timezone.utc)
            await self.session.flush()

    async def _get_connection_record(self, provider_name: str) -> MCPConnection | None:
        stmt = select(MCPConnection).where(MCPConnection.provider == provider_name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create_connection(self, provider_name: str) -> MCPConnection:
        conn = await self._get_connection_record(provider_name)
        if conn is None:
            conn = MCPConnection(provider=provider_name, status="disconnected")
            self.session.add(conn)
            await self.session.flush()
        return conn

    async def _persist_primary_user(self, email: str, name: str | None) -> None:
        """Store primary_user_email in app_settings and ensure self profile."""
        from app.config import settings as app_cfg

        email_lower = email.lower()

        for key, value in [("primary_user_email", email_lower), ("primary_user_name", name or "")]:
            if not value:
                continue
            stmt = select(AppSetting).where(AppSetting.key == key)
            result = await self.session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                self.session.add(AppSetting(key=key, value=value, is_secret=False))
            setattr(app_cfg, key, value)

        await self._ensure_self_profile(email_lower, name)
        await self.session.flush()
        logger.info("Primary user set to %s (%s)", email_lower, name or "no name")

    async def _ensure_self_profile(self, email: str, name: str | None) -> None:
        """Guarantee exactly one Profile(type='self') with the given email."""
        # Check if a profile with this email already exists
        stmt = select(Profile).where(func.lower(Profile.email) == email)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        # Find any current self profile
        stmt = select(Profile).where(Profile.type == "self")
        result = await self.session.execute(stmt)
        current_self = result.scalar_one_or_none()

        if existing and existing.type == "self":
            if name and (existing.name == "Me" or not existing.name):
                existing.name = name
            return

        if existing:
            existing.type = "self"
            if name and not existing.name:
                existing.name = name
            if current_self and current_self.id != existing.id:
                current_self.type = "contact"
            return

        if current_self:
            if current_self.email and current_self.email.lower() != email:
                current_self.type = "contact"
                self.session.add(Profile(
                    id=uuid.uuid4(),
                    type="self",
                    name=name or "Me",
                    email=email,
                    bio="Your personal profile. Enriched as you use the system.",
                    traits={"meeting_count": 0},
                    learning_log=[],
                ))
            else:
                current_self.email = email
                if name and (current_self.name == "Me" or not current_self.name):
                    current_self.name = name
        else:
            self.session.add(Profile(
                id=uuid.uuid4(),
                type="self",
                name=name or "Me",
                email=email,
                bio="Your personal profile. Enriched as you use the system.",
                traits={"meeting_count": 0},
                learning_log=[],
            ))
