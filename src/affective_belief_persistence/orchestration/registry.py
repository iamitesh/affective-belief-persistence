"""Typed specialist-agent registry and repository write authorization."""

from __future__ import annotations

from collections.abc import Iterable, Set
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.config import ConfigError, load_yaml
from affective_belief_persistence.orchestration.contracts import OrchestrationModel

AgentKind = Literal["supervisor", "specialist", "subagent"]
AgentRole = Literal[
    "supervisor",
    "research",
    "data",
    "engineering",
    "evaluation",
    "reviewer",
]


class AgentRegistryError(ValueError):
    """Base error for invalid registry data or registry operations."""


class AgentNotFoundError(AgentRegistryError):
    """The requested agent identifier is not registered."""


class AgentSelectionError(AgentRegistryError):
    """No available agent satisfies a task's declared requirements."""


class AgentAuthorizationError(AgentRegistryError):
    """An agent requested a repository path outside its write scope."""


def normalize_repository_path(path: str) -> str:
    """Return a canonical repository-relative path or raise an explicit error."""

    candidate = path.strip()
    if not candidate:
        raise AgentAuthorizationError("repository path cannot be empty")
    if "\\" in candidate:
        raise AgentAuthorizationError(f"repository path must use '/' separators: {path}")
    pure_path = PurePosixPath(candidate)
    if pure_path.is_absolute():
        raise AgentAuthorizationError(f"repository path must be relative: {path}")
    if any(part in {"", ".", ".."} for part in pure_path.parts):
        raise AgentAuthorizationError(f"repository path is not canonical: {path}")
    if any(character in candidate for character in "*?[]"):
        raise AgentAuthorizationError(f"concrete repository path cannot contain wildcards: {path}")
    if pure_path.parts[0] == ".git":
        raise AgentAuthorizationError("agents cannot write Git metadata")
    return pure_path.as_posix()


def normalize_allowed_path(pattern: str) -> str:
    """Validate an exact path or a terminal ``/**`` subtree pattern."""

    candidate = pattern.strip().rstrip("/")
    subtree = candidate.endswith("/**")
    prefix = candidate[:-3] if subtree else candidate
    if any(character in prefix for character in "*?[]"):
        raise AgentAuthorizationError(
            f"allowed path supports wildcards only as a terminal '/**': {pattern}"
        )
    normalized = normalize_repository_path(prefix)
    return f"{normalized}/**" if subtree else normalized


def path_is_allowed(path: str, allowed_paths: Iterable[str]) -> bool:
    """Return whether a concrete path is covered by at least one allowed scope."""

    normalized = normalize_repository_path(path)
    for raw_pattern in allowed_paths:
        pattern = normalize_allowed_path(raw_pattern)
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return True
        elif normalized == pattern:
            return True
    return False


class AgentDefinition(OrchestrationModel):
    """A specialist's selection, permission, and handoff contract."""

    agent_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    kind: AgentKind
    role: AgentRole
    supported_task_types: tuple[str, ...] = Field(min_length=1)
    allowed_paths: tuple[str, ...] = Field(min_length=1)
    required_input_schemas: tuple[str, ...] = ()
    output_schemas: tuple[str, ...] = ()
    default_timebox_seconds: int = Field(ge=1)
    retry_budget: int = Field(ge=0, le=2)
    escalation_destination: str = Field(min_length=1)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_contract(self) -> AgentDefinition:
        if len(self.supported_task_types) != len(set(self.supported_task_types)):
            raise ValueError("supported task types must be unique")
        normalized_paths = tuple(normalize_allowed_path(path) for path in self.allowed_paths)
        if len(normalized_paths) != len(set(normalized_paths)):
            raise ValueError("allowed paths must be unique")
        if self.kind == "supervisor" and self.role != "supervisor":
            raise ValueError("a supervisor-kind agent must have the supervisor role")
        return self

    def allows_path(self, path: str) -> bool:
        """Return whether this agent may write a repository-relative path."""

        return path_is_allowed(path, self.allowed_paths)

    def assert_paths_allowed(self, paths: Iterable[str]) -> None:
        """Raise with all unauthorized paths so callers can emit one failure event."""

        denied = sorted({path for path in paths if not self.allows_path(path)})
        if denied:
            joined = ", ".join(denied)
            raise AgentAuthorizationError(
                f"agent '{self.agent_id}' is not authorized to write: {joined}"
            )


class AgentRegistryConfig(OrchestrationModel):
    """Machine-readable registry document."""

    schema_version: Literal["1.0"]
    max_concurrent_workers: int = Field(ge=1, le=3)
    agents: tuple[AgentDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_agents(self) -> AgentRegistryConfig:
        identifiers = [agent.agent_id for agent in self.agents]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("agent identifiers must be unique")
        supervisors = [agent for agent in self.agents if agent.kind == "supervisor"]
        if len(supervisors) != 1:
            raise ValueError("registry must contain exactly one supervisor")
        return self


class AgentRegistry:
    """Deterministic lookup and selection over a validated registry config."""

    def __init__(self, config: AgentRegistryConfig) -> None:
        self._config = config
        self._by_id = {agent.agent_id: agent for agent in config.agents}

    @classmethod
    def load(cls, path: Path) -> AgentRegistry:
        """Load a registry using the foundation's duplicate-safe YAML parser."""

        try:
            data = load_yaml(path)
            config = AgentRegistryConfig.model_validate(data)
        except (ConfigError, ValueError) as exc:
            raise AgentRegistryError(f"invalid agent registry {path}: {exc}") from exc
        return cls(config)

    @property
    def max_workers(self) -> int:
        return self._config.max_concurrent_workers

    @property
    def max_retries(self) -> int:
        return max(agent.retry_budget for agent in self._config.agents)

    @property
    def agents(self) -> tuple[AgentDefinition, ...]:
        return self._config.agents

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._by_id[agent_id]
        except KeyError as exc:
            raise AgentNotFoundError(f"agent is not registered: {agent_id}") from exc

    def select(
        self,
        role: str,
        active_agent_ids: Set[str] | None = None,
        *,
        task_type: str | None = None,
        required_paths: Iterable[str] = (),
    ) -> AgentDefinition:
        """Select the first eligible agent in stable identifier order.

        The active set lets the scheduler avoid assigning a second task to a busy
        specialist. Concurrency itself remains a scheduler/lease-manager invariant.
        """

        active = active_agent_ids or frozenset()
        requested_paths = tuple(required_paths)
        candidates = []
        for agent in self._config.agents:
            if not agent.enabled or agent.agent_id in active or agent.role != role:
                continue
            if task_type is not None and task_type not in agent.supported_task_types:
                continue
            if any(not agent.allows_path(path) for path in requested_paths):
                continue
            candidates.append(agent)
        if not candidates:
            task_detail = f" and task type '{task_type}'" if task_type is not None else ""
            raise AgentSelectionError(f"no available agent for role '{role}'{task_detail}")
        return min(candidates, key=lambda agent: agent.agent_id)

    def assert_paths_allowed(self, agent_id: str, paths: Iterable[str]) -> None:
        self.get(agent_id).assert_paths_allowed(paths)


def load_agent_registry(path: Path) -> AgentRegistry:
    """Functional loader for callers that do not retain configuration classes."""

    return AgentRegistry.load(path)


def select_agent(
    registry: AgentRegistry,
    role: str,
    active_agent_ids: Set[str] | None = None,
    *,
    task_type: str | None = None,
    required_paths: Iterable[str] = (),
) -> AgentDefinition:
    """Functional selection wrapper used by simple schedulers."""

    return registry.select(
        role,
        active_agent_ids,
        task_type=task_type,
        required_paths=required_paths,
    )
