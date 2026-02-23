from __future__ import annotations

import importlib
import logging
import pkgutil

from app.mcp.base import BaseMCPProvider, ProviderStatus

logger = logging.getLogger(__name__)


class MCPRegistry:
    """Registry that auto-discovers and manages MCP provider instances."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseMCPProvider] = {}

    def register(self, provider: BaseMCPProvider) -> None:
        if not provider.name:
            raise ValueError(f"Provider {provider.__class__.__name__} must define a 'name'")
        if provider.name in self._providers:
            raise ValueError(f"Provider '{provider.name}' is already registered")
        self._providers[provider.name] = provider
        logger.info("Registered MCP provider: %s", provider.name)

    def get(self, name: str) -> BaseMCPProvider:
        if name not in self._providers:
            raise KeyError(f"MCP provider '{name}' not found in registry")
        return self._providers[name]

    def list_all(self) -> list[BaseMCPProvider]:
        return list(self._providers.values())

    def auto_discover(self, package_path: str = "app.mcp.providers") -> None:
        """Import all modules in the providers package to trigger registration."""
        try:
            package = importlib.import_module(package_path)
        except ModuleNotFoundError:
            logger.warning("MCP providers package '%s' not found", package_path)
            return

        for _importer, module_name, _is_pkg in pkgutil.iter_modules(
            package.__path__, prefix=f"{package_path}."
        ):
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseMCPProvider)
                        and attr is not BaseMCPProvider
                        and attr.name
                        and attr.name not in self._providers
                    ):
                        self.register(attr())
            except Exception:
                logger.exception("Failed to import MCP provider module: %s", module_name)

    async def health_check_all(self) -> dict[str, ProviderStatus]:
        """Run health checks on all registered providers."""
        results: dict[str, ProviderStatus] = {}
        for name, provider in self._providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception:
                logger.exception("Health check failed for provider: %s", name)
                results[name] = ProviderStatus.DISCONNECTED
        return results
