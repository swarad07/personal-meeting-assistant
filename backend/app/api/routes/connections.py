from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_connection_service
from app.services.connection_service import ConnectionService

router = APIRouter()


class AuthUrlRequest(BaseModel):
    redirect_uri: str = "http://localhost:3000/settings/connections/callback"


class AuthUrlResponse(BaseModel):
    auth_url: str | None


class CallbackRequest(BaseModel):
    code: str
    redirect_uri: str = "http://localhost:3000/settings/connections/callback"


class ConnectTokensRequest(BaseModel):
    tokens: dict[str, Any]


@router.get("/")
async def list_connections(
    service: ConnectionService = Depends(get_connection_service),
):
    """List all MCP providers and their connection status."""
    return await service.list_connections()


@router.post("/{provider}/auth-url", response_model=AuthUrlResponse)
async def get_auth_url(
    provider: str,
    body: AuthUrlRequest,
    service: ConnectionService = Depends(get_connection_service),
):
    """Get the OAuth authorization URL for a provider."""
    try:
        url = await service.get_auth_url(provider, body.redirect_uri)
        return AuthUrlResponse(auth_url=url)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")


@router.post("/{provider}/callback")
async def handle_callback(
    provider: str,
    body: CallbackRequest,
    service: ConnectionService = Depends(get_connection_service),
):
    """Exchange OAuth code for tokens and connect the provider."""
    try:
        connected = await service.handle_callback(provider, body.code, body.redirect_uri)
        return {"provider": provider, "connected": connected}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")


@router.post("/{provider}/connect")
async def connect_with_tokens(
    provider: str,
    body: ConnectTokensRequest,
    service: ConnectionService = Depends(get_connection_service),
):
    """Connect a provider with tokens directly (for API key auth or testing)."""
    try:
        connected = await service.connect_with_tokens(provider, body.tokens)
        return {"provider": provider, "connected": connected}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")


@router.delete("/{provider}")
async def disconnect_provider(
    provider: str,
    service: ConnectionService = Depends(get_connection_service),
):
    """Disconnect a provider and clear stored tokens."""
    try:
        await service.disconnect(provider)
        return {"provider": provider, "status": "disconnected"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")


@router.get("/{provider}/health")
async def check_health(
    provider: str,
    service: ConnectionService = Depends(get_connection_service),
):
    """Check the health of a specific provider."""
    try:
        return await service.check_health(provider)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")
