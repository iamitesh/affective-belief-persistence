"""Typed, serializable contracts shared by orchestration components.

The orchestration package deliberately exchanges explicit data contracts rather
than agent conversation history.  Every model in this module rejects unknown
fields and is immutable at the model boundary so checkpoints fail loudly when
their shape drifts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

SchemaVersion = Literal["1.0"]
Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Scalar: TypeAlias = str | int | float | bool | None


class OrchestrationModel(BaseModel):
    """Base contract with forward-compatible JSON serialization semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskStatus(StrEnum):
    """Lifecycle states defined by the research workflow PRD."""

    PENDING = "pending"
    READY = "ready"
    LEASED = "leased"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    RETRY = "retry"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ValidationStatus(StrEnum):
    """Validation state for a produced artifact or handoff."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class FailureCategory(StrEnum):
    """Structured failure classes used for retry and escalation policy."""

    VALIDATION_FAILURE = "validation_failure"
    DEPENDENCY_MISSING = "dependency_missing"
    SCHEMA_MISMATCH = "schema_mismatch"
    FILE_LEASE_CONFLICT = "file_lease_conflict"
    MODEL_UNAVAILABLE = "model_unavailable"
    BUDGET_EXCEEDED = "budget_exceeded"
    REPRODUCIBILITY_FAILURE = "reproducibility_failure"
    SAFETY_BOUNDARY = "safety_boundary"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    RUNTIME_INTERRUPTED = "runtime_interrupted"


class TaskBudget(OrchestrationModel):
    """Hard limits assigned to one task."""

    max_attempts: int = Field(default=2, ge=1, le=3)
    max_runtime_seconds: int = Field(ge=1)
    max_tokens: int = Field(default=0, ge=0)
    max_cost_usd: float = Field(default=0, ge=0)
    required_gpu_hours: float = Field(default=0, ge=0)


class TaskContract(OrchestrationModel):
    """Static specification used by the graph and scheduler."""

    task_id: Identifier
    issue_number: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1)
    owner: Identifier
    task_type: Identifier
    gate_id: Identifier | None = None
    dependencies: tuple[Identifier, ...] = ()
    optional_dependencies: tuple[Identifier, ...] = ()
    optional: bool = False
    authorized_files: tuple[str, ...] = ()
    output_paths: tuple[str, ...] = ()
    input_artifact_ids: tuple[Identifier, ...] = ()
    expected_artifact_ids: tuple[Identifier, ...] = ()
    acceptance_tests: tuple[str, ...] = Field(min_length=1)
    budget: TaskBudget

    @model_validator(mode="after")
    def validate_collections(self) -> TaskContract:
        collections = {
            "dependencies": self.dependencies,
            "optional_dependencies": self.optional_dependencies,
            "authorized_files": self.authorized_files,
            "output_paths": self.output_paths,
            "input_artifact_ids": self.input_artifact_ids,
            "expected_artifact_ids": self.expected_artifact_ids,
            "acceptance_tests": self.acceptance_tests,
        }
        for name, values in collections.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicates")
        if self.task_id in self.dependencies:
            raise ValueError("a task cannot depend on itself")
        if self.task_id in self.optional_dependencies:
            raise ValueError("a task cannot optionally depend on itself")
        overlap = set(self.dependencies) & set(self.optional_dependencies)
        if overlap:
            raise ValueError("required and optional dependencies must be disjoint")
        if len(self.expected_artifact_ids) != len(self.output_paths):
            raise ValueError("expected_artifact_ids and output_paths must have equal lengths")
        return self


class ArtifactContract(OrchestrationModel):
    """Provenance and validation record for an artifact exchanged by agents."""

    schema_version: SchemaVersion = "1.0"
    artifact_id: Identifier
    produced_by_task: Identifier
    produced_by_agent: Identifier
    logical_name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    created_at: datetime
    source_commit: str = Field(min_length=1)
    downstream_task_ids: tuple[Identifier, ...] = ()
    sha256: Sha256 | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_notes: tuple[str, ...] = ()
    metadata: dict[str, Scalar] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_digest_metadata(self) -> ArtifactContract:
        if (self.sha256 is None) != (self.size_bytes is None):
            raise ValueError("sha256 and size_bytes must either both be set or both be absent")
        if len(self.downstream_task_ids) != len(set(self.downstream_task_ids)):
            raise ValueError("downstream_task_ids must not contain duplicates")
        return self


class HandoffContract(OrchestrationModel):
    """Explicit transfer of validated outputs between two tasks."""

    handoff_id: Identifier
    from_task_id: Identifier
    to_task_id: Identifier
    artifact_ids: tuple[Identifier, ...] = Field(min_length=1)
    summary: str = Field(min_length=1)
    created_at: datetime
    validation_status: ValidationStatus = ValidationStatus.PENDING
    acceptance_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_handoff(self) -> HandoffContract:
        if self.from_task_id == self.to_task_id:
            raise ValueError("a handoff must transfer work to a different task")
        if len(self.artifact_ids) != len(set(self.artifact_ids)):
            raise ValueError("artifact_ids must not contain duplicates")
        return self


class WorkerArtifactProposal(OrchestrationModel):
    """Artifact bytes proposed by a worker for supervisor validation and writing."""

    artifact_id: Identifier
    logical_name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    content: str


class WorkerResult(OrchestrationModel):
    """Immutable result envelope; workers cannot return shared workflow state."""

    task_id: Identifier
    succeeded: bool
    artifacts: tuple[WorkerArtifactProposal, ...] = ()
    consumed_artifact_ids: tuple[Identifier, ...] = ()
    passed_checks: tuple[str, ...] = ()
    no_artifact_reason: str | None = Field(default=None, min_length=1)
    error: str | None = Field(default=None, min_length=1)
    failure_category: FailureCategory | None = None
    retryable: bool = False
    tokens_used: int = Field(default=0, ge=0)
    gpu_hours_used: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_result_shape(self) -> WorkerResult:
        if self.succeeded:
            if self.error is not None or self.failure_category is not None or self.retryable:
                raise ValueError("successful results cannot carry failure metadata")
            if self.artifacts and self.no_artifact_reason is not None:
                raise ValueError("successful results must provide artifacts or a reason, not both")
        else:
            if self.error is None or self.failure_category is None:
                raise ValueError("failed results require an error and failure_category")
            if self.artifacts or self.no_artifact_reason is not None:
                raise ValueError("failed results cannot propose artifacts or no-artifact success")
        identifiers = [artifact.artifact_id for artifact in self.artifacts]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("worker artifact IDs must be unique")
        return self


class WorkflowContract(OrchestrationModel):
    """Static workflow definition from which checkpoint state is initialized."""

    schema_version: SchemaVersion = "1.0"
    workflow_id: Identifier
    sprint_id: Identifier
    tasks: tuple[TaskContract, ...] = Field(min_length=1)
    max_workers: int = Field(default=3, ge=1, le=3)
    created_at: datetime

    @model_validator(mode="after")
    def validate_task_ids(self) -> WorkflowContract:
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("workflow task IDs must be unique")
        return self


# Concise public names for scheduler and persistence integrations.
Artifact = ArtifactContract
Handoff = HandoffContract
