from abc import ABC, abstractmethod
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Shared state flowing through LangGraph pipelines.

    Uses Any for db_session/neo4j_driver/mcp_registry to avoid forward-reference
    issues with LangGraph's StateGraph type introspection.
    """

    trigger: str
    trigger_params: dict[str, Any]

    new_meeting_ids: list[str]
    updated_meeting_ids: list[str]
    skipped_meeting_ids: list[str]

    extracted_entities: list[dict[str, Any]]
    resolved_entities: list[dict[str, Any]]
    extracted_action_items: list[dict[str, Any]]

    new_relationships: list[dict[str, Any]]
    updated_relationships: list[dict[str, Any]]

    upcoming_meetings: list[dict[str, Any]]
    briefing: dict[str, Any] | None

    search_results: list[dict[str, Any]]
    synthesis: str | None

    errors: list[dict[str, Any]]

    mcp_registry: Any
    db_session: Any
    neo4j_driver: Any


class BaseAgent(ABC):
    """Abstract base class for all AI agents.

    Subclasses declare their pipeline membership, dependencies, and required
    MCP providers. The AgentRegistry uses these declarations to build
    per-pipeline LangGraph StateGraphs automatically.
    """

    name: str = ""
    description: str = ""
    pipeline: str = "sync"  # "sync" | "briefing" | "on_demand"
    dependencies: list[str] = []
    required_mcp_providers: list[str] = []

    @abstractmethod
    async def should_run(self, state: AgentState) -> bool:
        """Return True if this agent should execute given the current state."""
        ...

    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        """Execute the agent's logic and return updated state.

        Implementations must handle errors per-item (per-meeting) and append
        failures to state["errors"] rather than raising.
        """
        ...
