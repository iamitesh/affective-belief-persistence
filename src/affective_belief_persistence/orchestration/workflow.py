"""Loading and validation for the bounded 48-hour sprint workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.orchestration.budgets import BudgetLimits
from affective_belief_persistence.orchestration.contracts import (
    Identifier,
    OrchestrationModel,
    TaskContract,
    WorkflowContract,
)
from affective_belief_persistence.orchestration.graph import DependencyGraph


class WorkflowDefinitionError(ValueError):
    """A workflow file cannot safely initialize a supervisor."""


class GateDefinition(OrchestrationModel):
    """File-backed evidence required to pass one integration gate."""

    gate_id: Identifier
    name: str = Field(min_length=1)
    task_id: Identifier
    required_evidence_artifact_ids: tuple[Identifier, ...] = Field(min_length=1)


class WorkflowDefinition(OrchestrationModel):
    """Complete sprint definition, including graph, agents, budgets, and gates."""

    schema_version: Literal["1.0"] = "1.0"
    workflow_id: Identifier
    sprint_id: Identifier
    seed: int = Field(ge=0, le=2**63 - 1)
    created_at: str = Field(min_length=1)
    agent_registry: str = Field(min_length=1)
    max_workers: int = Field(default=3, ge=1, le=3)
    limits: BudgetLimits
    tasks: tuple[TaskContract, ...] = Field(min_length=1)
    gates: tuple[GateDefinition, ...] = Field(min_length=1)
    final_task_id: Identifier

    @model_validator(mode="after")
    def validate_definition(self) -> WorkflowDefinition:
        from datetime import datetime

        try:
            created_at = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO-8601 timestamp") from exc
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        graph = DependencyGraph(self.tasks)
        if self.final_task_id not in graph.task_ids:
            raise ValueError("final_task_id must name a declared task")
        task_by_id = {task.task_id: task for task in self.tasks}
        gate_ids = [gate.gate_id for gate in self.gates]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("gate IDs must be unique")
        for gate in self.gates:
            task = task_by_id.get(gate.task_id)
            if task is None or task.gate_id != gate.gate_id:
                raise ValueError(f"gate '{gate.gate_id}' must map to its declared gate task")
            missing = set(gate.required_evidence_artifact_ids) - set(task.input_artifact_ids)
            if missing:
                raise ValueError(
                    f"gate '{gate.gate_id}' evidence is not declared as task input: "
                    + ", ".join(sorted(missing))
                )
        for task in self.tasks:
            if not task.authorized_files:
                raise ValueError(f"task '{task.task_id}' requires at least one leased path")
            if task.budget.required_gpu_hours > 0 and not task.optional:
                raise ValueError("GPU-dependent tasks must be optional in the mandatory MVP")
        return self

    def contract(self) -> WorkflowContract:
        """Return the static subset used to initialize checkpoint state."""

        from datetime import datetime

        created_at = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        return WorkflowContract(
            workflow_id=self.workflow_id,
            sprint_id=self.sprint_id,
            tasks=self.tasks,
            max_workers=self.max_workers,
            created_at=created_at,
        )


@dataclass(frozen=True)
class LoadedWorkflow:
    definition: WorkflowDefinition
    project_root: Path
    source_path: Path
    registry_path: Path
    config_sha256: str


def _approved_config_path(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    config_root = (root / "configs").resolve()
    if not resolved.is_relative_to(config_root):
        raise WorkflowDefinitionError(f"workflow reference escapes configs/: {path}")
    return resolved


def load_workflow_definition(path: Path) -> LoadedWorkflow:
    """Load duplicate-safe YAML and validate every graph and path contract."""

    from affective_belief_persistence.config import ConfigError, find_project_root, load_yaml

    try:
        root = find_project_root(path)
        source = _approved_config_path(root, path)
        definition = WorkflowDefinition.model_validate(load_yaml(source))
        registry = _approved_config_path(root, root / definition.agent_registry)
        if not registry.is_file():
            raise WorkflowDefinitionError(f"agent registry does not exist: {registry}")
    except (ConfigError, ValueError) as exc:
        if isinstance(exc, WorkflowDefinitionError):
            raise
        raise WorkflowDefinitionError(f"invalid workflow definition {path}: {exc}") from exc
    return LoadedWorkflow(
        definition=definition,
        project_root=root,
        source_path=source,
        registry_path=registry,
        config_sha256=sha256_value(definition.model_dump(mode="json")),
    )
