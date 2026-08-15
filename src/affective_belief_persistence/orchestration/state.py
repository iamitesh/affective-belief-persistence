"""Checkpoint-safe workflow state and lifecycle transitions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType

from pydantic import Field, model_validator

from affective_belief_persistence.orchestration.contracts import (
    ArtifactContract,
    FailureCategory,
    HandoffContract,
    Identifier,
    OrchestrationModel,
    SchemaVersion,
    TaskStatus,
    WorkflowContract,
)
from affective_belief_persistence.orchestration.events import EventLog, WorkflowEvent

ALLOWED_TASK_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = MappingProxyType(
    {
        TaskStatus.PENDING: frozenset({TaskStatus.READY, TaskStatus.BLOCKED}),
        TaskStatus.READY: frozenset({TaskStatus.LEASED, TaskStatus.BLOCKED}),
        TaskStatus.LEASED: frozenset({TaskStatus.RUNNING}),
        TaskStatus.RUNNING: frozenset({TaskStatus.VALIDATING}),
        TaskStatus.VALIDATING: frozenset(
            {TaskStatus.COMPLETED, TaskStatus.RETRY, TaskStatus.BLOCKED}
        ),
        TaskStatus.RETRY: frozenset({TaskStatus.READY, TaskStatus.BLOCKED}),
        TaskStatus.BLOCKED: frozenset({TaskStatus.ESCALATED}),
        TaskStatus.ESCALATED: frozenset({TaskStatus.READY, TaskStatus.CANCELLED}),
        TaskStatus.COMPLETED: frozenset(),
        TaskStatus.CANCELLED: frozenset(),
    }
)


class InvalidTaskTransition(ValueError):
    """Raised when a scheduler requests a lifecycle edge not in the PRD."""


class TaskLease(OrchestrationModel):
    """Exclusive, expiring assignment of a task and its file scope to a worker."""

    lease_id: Identifier
    worker_id: Identifier
    acquired_at: datetime
    expires_at: datetime
    authorized_files: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_window(self) -> TaskLease:
        if self.expires_at <= self.acquired_at:
            raise ValueError("lease expiry must be after acquisition")
        return self


class WorkflowTask(OrchestrationModel):
    """Mutable-in-time task facts represented as an immutable snapshot."""

    task_id: Identifier
    issue_number: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1)
    owner: Identifier = "unassigned"
    task_type: Identifier = "unspecified"
    gate_id: Identifier | None = None
    dependencies: tuple[Identifier, ...] = ()
    optional_dependencies: tuple[Identifier, ...] = ()
    optional: bool = False
    authorized_files: tuple[str, ...] = ()
    output_paths: tuple[str, ...] = ()
    input_artifact_ids: tuple[Identifier, ...] = ()
    expected_artifact_ids: tuple[Identifier, ...] = ()
    acceptance_tests: tuple[str, ...] = ()
    max_attempts: int = Field(default=2, ge=1, le=3)
    max_runtime_seconds: int = Field(default=1, ge=1)
    status: TaskStatus = TaskStatus.PENDING
    attempt_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    lease: TaskLease | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    output_artifact_ids: tuple[Identifier, ...] = ()
    blocker: str | None = Field(default=None, min_length=1)
    last_error: str | None = Field(default=None, min_length=1)
    failure_category: FailureCategory | None = None
    no_artifact_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_state_invariants(self) -> WorkflowTask:
        if self.status in {TaskStatus.LEASED, TaskStatus.RUNNING, TaskStatus.VALIDATING}:
            if self.lease is None:
                raise ValueError(f"{self.status.value} tasks require an active lease")
        elif self.lease is not None:
            raise ValueError(f"{self.status.value} tasks cannot retain an active lease")
        if self.status is TaskStatus.COMPLETED and self.completed_at is None:
            raise ValueError("completed tasks require completed_at")
        if self.status is not TaskStatus.COMPLETED and self.completed_at is not None:
            raise ValueError("only completed tasks may set completed_at")
        if self.status is TaskStatus.BLOCKED and self.blocker is None:
            raise ValueError("blocked tasks require a blocker")
        if len(self.output_artifact_ids) != len(set(self.output_artifact_ids)):
            raise ValueError("output artifact IDs must be unique")
        if self.output_artifact_ids and self.no_artifact_reason is not None:
            raise ValueError("a task with output artifacts cannot set no_artifact_reason")
        if self.failure_category is not None and self.last_error is None:
            raise ValueError("failure_category requires last_error")
        return self

    def transition(
        self,
        target: TaskStatus,
        *,
        at: datetime,
        lease: TaskLease | None = None,
        blocker: str | None = None,
        error: str | None = None,
        failure_category: FailureCategory | None = None,
        output_artifact_ids: tuple[Identifier, ...] | None = None,
        no_artifact_reason: str | None = None,
    ) -> WorkflowTask:
        """Return the next valid task snapshot without mutating this one."""

        optional_cancel = (
            self.optional
            and target is TaskStatus.CANCELLED
            and self.status
            in {
                TaskStatus.PENDING,
                TaskStatus.READY,
            }
        )
        if target not in ALLOWED_TASK_TRANSITIONS[self.status] and not optional_cancel:
            raise InvalidTaskTransition(f"cannot transition {self.status.value} -> {target.value}")
        if (
            target is TaskStatus.CANCELLED
            and self.status is not TaskStatus.ESCALATED
            and not self.optional
        ):
            raise InvalidTaskTransition("only optional tasks may be cancelled before escalation")
        if target is TaskStatus.CANCELLED and no_artifact_reason is None:
            raise InvalidTaskTransition("cancelled tasks require no_artifact_reason")
        if failure_category is not None and error is None:
            raise InvalidTaskTransition("failure_category requires an error")

        active_lease = self.lease
        attempt_count = self.attempt_count
        retry_count = self.retry_count
        started_at = self.started_at
        completed_at: datetime | None = None

        if target is TaskStatus.LEASED:
            if lease is None:
                raise InvalidTaskTransition("ready -> leased requires a lease")
            active_lease = lease
        elif lease is not None:
            raise InvalidTaskTransition("a new lease may only be supplied when entering leased")

        if target is TaskStatus.RUNNING:
            attempt_count += 1
            started_at = at
        if target is TaskStatus.RETRY:
            retry_count += 1
        if target in {
            TaskStatus.COMPLETED,
            TaskStatus.RETRY,
            TaskStatus.BLOCKED,
            TaskStatus.ESCALATED,
            TaskStatus.CANCELLED,
        }:
            active_lease = None
        if target is TaskStatus.COMPLETED:
            completed_at = at

        return self.model_copy(
            update={
                "status": target,
                "attempt_count": attempt_count,
                "retry_count": retry_count,
                "lease": active_lease,
                "started_at": started_at,
                "completed_at": completed_at,
                "updated_at": at,
                "blocker": blocker if target is TaskStatus.BLOCKED else None,
                "last_error": error if error is not None else self.last_error,
                "failure_category": failure_category if error is not None else None,
                "output_artifact_ids": (
                    output_artifact_ids
                    if output_artifact_ids is not None
                    else self.output_artifact_ids
                ),
                "no_artifact_reason": no_artifact_reason,
            }
        )

    def recover_to_ready(self, *, at: datetime, reason: str) -> WorkflowTask:
        """Recover an interrupted active task without pretending work completed.

        This dedicated operation is intentionally separate from normal lifecycle
        transitions.  It is valid only after a process interruption while a task
        was leased, running, or validating, and clears the stale lease.
        """

        if self.status not in {TaskStatus.LEASED, TaskStatus.RUNNING, TaskStatus.VALIDATING}:
            raise InvalidTaskTransition(f"cannot recover {self.status.value} -> ready")
        return self.model_copy(
            update={
                "status": TaskStatus.READY,
                "lease": None,
                "completed_at": None,
                "updated_at": at,
                "last_error": reason,
                "failure_category": FailureCategory.RUNTIME_INTERRUPTED,
                "blocker": None,
            }
        )


# Backward-compatible descriptive name for callers that model task state separately.
TaskState = WorkflowTask


class WorkflowState(OrchestrationModel):
    """Complete state snapshot suitable for an atomic JSON checkpoint."""

    schema_version: SchemaVersion = "1.0"
    workflow_id: Identifier
    sprint_id: Identifier
    revision: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    phase: str = "initializing"
    deadline: datetime | None = None
    active_agents: tuple[Identifier, ...] = ()
    budget_usage: dict[str, int | float] = Field(default_factory=dict)
    gates: dict[str, bool] = Field(default_factory=dict)
    blockers: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    current_commit: str = "unknown"
    checkpoint_sequence: int = Field(default=0, ge=0)
    tasks: dict[str, WorkflowTask]
    artifacts: dict[str, ArtifactContract] = Field(default_factory=dict)
    handoffs: tuple[HandoffContract, ...] = ()
    event_log: EventLog

    @model_validator(mode="after")
    def validate_snapshot(self) -> WorkflowState:
        if self.event_log.workflow_id != self.workflow_id:
            raise ValueError("event log must belong to the workflow")
        if any(key != task.task_id for key, task in self.tasks.items()):
            raise ValueError("task map keys must equal contained task IDs")
        if any(key != artifact.artifact_id for key, artifact in self.artifacts.items()):
            raise ValueError("artifact map keys must equal contained artifact IDs")
        if len({handoff.handoff_id for handoff in self.handoffs}) != len(self.handoffs):
            raise ValueError("handoff IDs must be unique")
        return self

    @classmethod
    def from_contract(cls, contract: WorkflowContract) -> WorkflowState:
        """Initialize pending task state from a validated static contract."""

        tasks = {
            task.task_id: WorkflowTask(
                task_id=task.task_id,
                issue_number=task.issue_number,
                title=task.title,
                owner=task.owner,
                task_type=task.task_type,
                gate_id=task.gate_id,
                dependencies=task.dependencies,
                optional_dependencies=task.optional_dependencies,
                optional=task.optional,
                authorized_files=task.authorized_files,
                output_paths=task.output_paths,
                input_artifact_ids=task.input_artifact_ids,
                expected_artifact_ids=task.expected_artifact_ids,
                acceptance_tests=task.acceptance_tests,
                max_attempts=task.budget.max_attempts,
                max_runtime_seconds=task.budget.max_runtime_seconds,
                updated_at=contract.created_at,
            )
            for task in contract.tasks
        }
        return cls(
            workflow_id=contract.workflow_id,
            sprint_id=contract.sprint_id,
            created_at=contract.created_at,
            updated_at=contract.created_at,
            tasks=tasks,
            event_log=EventLog(workflow_id=contract.workflow_id),
        )

    def replace_task(self, task: WorkflowTask) -> WorkflowState:
        """Return a new revision containing one updated task snapshot."""

        if task.task_id not in self.tasks:
            raise KeyError(f"unknown task: {task.task_id}")
        tasks = {**self.tasks, task.task_id: task}
        return self.model_copy(
            update={"tasks": tasks, "revision": self.revision + 1, "updated_at": task.updated_at}
        )

    def append_event(self, event: WorkflowEvent) -> WorkflowState:
        """Return a new revision with an event appended to the audit log."""

        event_log = self.event_log.append(event)
        return self.model_copy(
            update={
                "event_log": event_log,
                "revision": self.revision + 1,
                "updated_at": event.occurred_at,
            }
        )

    def to_checkpoint_json(self) -> str:
        """Serialize a canonical JSON checkpoint with enum and datetime encoding."""

        return self.model_dump_json(indent=2)

    @classmethod
    def from_checkpoint_json(cls, checkpoint: str | bytes) -> WorkflowState:
        """Validate and restore a checkpoint; malformed state is rejected."""

        return cls.model_validate_json(checkpoint)
