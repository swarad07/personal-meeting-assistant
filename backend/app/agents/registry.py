from __future__ import annotations

import importlib
import logging
import pkgutil
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from app.agents.base import AgentState, BaseAgent

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry that auto-discovers agents and builds per-pipeline LangGraph graphs."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if not agent.name:
            raise ValueError(f"Agent {agent.__class__.__name__} must define a 'name'")
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")
        self._agents[agent.name] = agent
        logger.info("Registered agent: %s (pipeline=%s)", agent.name, agent.pipeline)

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not found in registry")
        return self._agents[name]

    def list_all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def list_by_pipeline(self, pipeline: str) -> list[BaseAgent]:
        return [a for a in self._agents.values() if a.pipeline == pipeline]

    def auto_discover(self, package_path: str = "app.agents") -> None:
        """Import all modules in the agents package to trigger registration."""
        try:
            package = importlib.import_module(package_path)
        except ModuleNotFoundError:
            logger.warning("Agent package '%s' not found", package_path)
            return

        for _importer, module_name, _is_pkg in pkgutil.iter_modules(
            package.__path__, prefix=f"{package_path}."
        ):
            if module_name.endswith((".base", ".registry")):
                continue
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseAgent)
                        and attr is not BaseAgent
                        and attr.name
                        and attr.name not in self._agents
                    ):
                        self.register(attr())
            except Exception:
                logger.exception("Failed to import agent module: %s", module_name)

    def resolve_dependencies(self, pipeline: str) -> list[str]:
        """Return topologically sorted agent names for a pipeline."""
        agents = self.list_by_pipeline(pipeline)
        graph: dict[str, set[str]] = {}
        pipeline_names = {a.name for a in agents}

        for agent in agents:
            deps_in_pipeline = {d for d in agent.dependencies if d in pipeline_names}
            graph[agent.name] = deps_in_pipeline

        sorter = TopologicalSorter(graph)
        return list(sorter.static_order())

    def build_graph(self, pipeline: str) -> StateGraph:
        """Build a LangGraph StateGraph for the given pipeline."""
        execution_order = self.resolve_dependencies(pipeline)
        if not execution_order:
            raise ValueError(f"No agents registered for pipeline '{pipeline}'")

        graph = StateGraph(AgentState)

        for agent_name in execution_order:
            agent = self._agents[agent_name]

            async def _node_fn(state: AgentState, _agent: BaseAgent = agent) -> AgentState:
                if not await _agent.should_run(state):
                    logger.info("Skipping agent %s (should_run=False)", _agent.name)
                    return state
                logger.info("Running agent: %s", _agent.name)
                return await _agent.process(state)

            graph.add_node(agent_name, _node_fn)

        graph.add_edge(START, execution_order[0])
        for i in range(len(execution_order) - 1):
            graph.add_edge(execution_order[i], execution_order[i + 1])
        graph.add_edge(execution_order[-1], END)

        return graph

    def validate(self) -> list[str]:
        """Validate all agent dependencies and MCP requirements. Returns list of issues."""
        issues: list[str] = []
        all_names = set(self._agents.keys())
        for agent in self._agents.values():
            for dep in agent.dependencies:
                if dep not in all_names:
                    issues.append(f"Agent '{agent.name}' depends on unknown agent '{dep}'")
        return issues
