"""Deterministic supervisor, bounded worker scheduler, and checkpoint recovery."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from affective_belief_persistence.determinism import canonical_json, sha256_file, sha256_value
from affective_belief_persistence.orchestration.budgets import (
    BudgetAccount,
    BudgetExceededError,
    BudgetRequest,
    BudgetUsage,
)
from affective_belief_persistence.orchestration.contracts import (
    ArtifactContract,
    FailureCategory,
    HandoffContract,
    OrchestrationModel,
    TaskContract,
    TaskStatus,
    ValidationStatus,
    WorkerArtifactProposal,
    WorkerResult,
)
from affective_belief_persistence.orchestration.events import (
    WorkflowEvent,
    WorkflowEventType,
)
from affective_belief_persistence.orchestration.graph import DependencyGraph
from affective_belief_persistence.orchestration.leases import (
    LeaseCapacityError,
    LeaseConflictError,
    PathLease,
    PathLeaseManager,
    ReleaseResult,
)
from affective_belief_persistence.orchestration.registry import (
    AgentRegistry,
    AgentSelectionError,
    load_agent_registry,
)
from affective_belief_persistence.orchestration.state import TaskLease, WorkflowState
from affective_belief_persistence.orchestration.validation import (
    ResultValidation,
    validate_worker_result,
)
from affective_belief_persistence.orchestration.workflow import GateDefinition, LoadedWorkflow
from affective_belief_persistence.provenance import collect_code_state


class OrchestrationError(RuntimeError):
    """The supervisor cannot safely advance the graph."""


class WorkflowExecutor(Protocol):
    """Specialists receive immutable inputs and return an immutable proposal."""

    def run(
        self,
        task: TaskContract,
        *,
        input_artifact_ids: tuple[str, ...],
        seed: int,
        attempt: int,
    ) -> WorkerResult: ...


class LogicalClock:
    """Monotonic logical UTC clock used by the offline reproducibility path."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("logical clock start must be timezone-aware")
        self._next = start.astimezone(UTC)

    def __call__(self) -> datetime:
        value = self._next
        self._next += timedelta(seconds=1)
        return value


class SyntheticWorkflowExecutor:
    """Offline deterministic specialist used to validate orchestration behavior."""

    def __init__(
        self,
        *,
        fail_through_attempt: Mapping[str, int] | None = None,
        failure_category: FailureCategory = FailureCategory.VALIDATION_FAILURE,
    ) -> None:
        self._failures = dict(fail_through_attempt or {})
        self._failure_category = failure_category

    def run(
        self,
        task: TaskContract,
        *,
        input_artifact_ids: tuple[str, ...],
        seed: int,
        attempt: int,
    ) -> WorkerResult:
        if attempt <= self._failures.get(task.task_id, 0):
            return WorkerResult(
                task_id=task.task_id,
                succeeded=False,
                error=f"deterministic injected failure on attempt {attempt}",
                failure_category=self._failure_category,
                retryable=True,
            )
        artifacts = []
        for artifact_id, path in zip(task.expected_artifact_ids, task.output_paths, strict=True):
            payload = {
                "artifact_id": artifact_id,
                "attempt": attempt,
                "input_artifact_ids": list(sorted(input_artifact_ids)),
                "offline": True,
                "seed": seed,
                "synthetic": True,
                "task_id": task.task_id,
                "task_type": task.task_type,
                "title": task.title,
            }
            artifacts.append(
                WorkerArtifactProposal(
                    artifact_id=artifact_id,
                    logical_name=artifact_id,
                    path=path,
                    media_type="application/json",
                    content=canonical_json(payload) + "\n",
                )
            )
        no_artifact_reason = None
        if not artifacts:
            no_artifact_reason = "task contract intentionally declares no output artifact"
        token_estimate = sum(max(1, len(artifact.content) // 4) for artifact in artifacts)
        return WorkerResult(
            task_id=task.task_id,
            succeeded=True,
            artifacts=tuple(artifacts),
            consumed_artifact_ids=tuple(sorted(input_artifact_ids)),
            passed_checks=task.acceptance_tests,
            no_artifact_reason=no_artifact_reason,
            tokens_used=token_estimate,
            gpu_hours_used=task.budget.required_gpu_hours,
        )


class WorkflowRunSummary(OrchestrationModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    status: Literal["completed", "paused", "failed"]
    state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_tasks: int = Field(ge=0)
    cancelled_tasks: int = Field(ge=0)
    escalated_tasks: int = Field(ge=0)
    checkpoint_sequence: int = Field(ge=0)


@dataclass(frozen=True)
class _ScheduledWork:
    task: TaskContract
    agent_id: str
    lease: PathLease
    input_artifact_ids: tuple[str, ...]
    attempt: int


class Supervisor:
    """Single writer for task state, events, budgets, leases, and artifacts."""

    def __init__(
        self,
        loaded: LoadedWorkflow,
        output_root: Path,
        *,
        executor: WorkflowExecutor | None = None,
        resume: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.loaded = loaded
        self.definition = loaded.definition
        self.graph = DependencyGraph(self.definition.tasks)
        self.registry: AgentRegistry = load_agent_registry(loaded.registry_path)
        self.output_root = output_root.resolve()
        self.executor = executor or SyntheticWorkflowExecutor()
        start = self.definition.contract().created_at
        self.clock = clock or LogicalClock(start)
        self.gates_by_task: dict[str, GateDefinition] = {
            gate.task_id: gate for gate in self.definition.gates
        }

        if resume:
            self.state = self._load_checkpoint()
            if clock is None:
                last_event_at = (
                    self.state.event_log.events[-1].occurred_at
                    if self.state.event_log.events
                    else self.state.updated_at
                )
                self.clock = LogicalClock(
                    max(self.state.updated_at, last_event_at) + timedelta(seconds=1)
                )
            usage = BudgetUsage.model_validate(self.state.budget_usage)
        else:
            self._prepare_output()
            code = collect_code_state(loaded.project_root)
            self.state = WorkflowState.from_contract(self.definition.contract()).model_copy(
                update={
                    "phase": "ready",
                    "deadline": self.definition.limits.deadline,
                    "gates": {gate.gate_id: False for gate in self.definition.gates},
                    "current_commit": code.commit,
                }
            )
            usage = BudgetUsage()
        self.leases = PathLeaseManager(
            max_workers=min(self.definition.max_workers, self.registry.max_workers),
            clock=self.clock,
        )
        self.budgets = BudgetAccount(
            self.definition.limits,
            usage=usage,
            started_at=start,
            clock=self.clock,
        )
        if resume:
            self._recover_interrupted_tasks()
        else:
            self._record_event(
                WorkflowEventType.WORKFLOW_CREATED,
                message="supervisor initialized validated workflow",
                payload={"config_sha256": loaded.config_sha256},
            )
        self._checkpoint()

    @property
    def checkpoint_path(self) -> Path:
        return self.output_root / "workflow-state.json"

    @property
    def events_path(self) -> Path:
        return self.output_root / "workflow-events.jsonl"

    def _prepare_output(self) -> None:
        if self.output_root.is_symlink():
            raise OrchestrationError("workflow output cannot be a symlink")
        if self.output_root.exists() and any(self.output_root.iterdir()):
            raise OrchestrationError(f"workflow output must be empty: {self.output_root}")
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _load_checkpoint(self) -> WorkflowState:
        if not self.checkpoint_path.is_file():
            raise OrchestrationError(f"resume checkpoint does not exist: {self.checkpoint_path}")
        try:
            state = WorkflowState.from_checkpoint_json(
                self.checkpoint_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise OrchestrationError(f"invalid workflow checkpoint: {exc}") from exc
        self.graph.validate_state(state)
        if state.workflow_id != self.definition.workflow_id:
            raise OrchestrationError("checkpoint belongs to a different workflow")
        return state

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise OrchestrationError("supervisor clock must return timezone-aware timestamps")
        return value.astimezone(UTC)

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    def _record_event(
        self,
        event_type: WorkflowEventType,
        *,
        task_id: str | None = None,
        previous_status: TaskStatus | None = None,
        new_status: TaskStatus | None = None,
        message: str | None = None,
        payload: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        sequence = self.state.event_log.next_sequence
        event = WorkflowEvent(
            event_id=f"event-{sequence:06d}",
            workflow_id=self.state.workflow_id,
            sequence=sequence,
            event_type=event_type,
            occurred_at=self._now(),
            actor_id="sprint-supervisor",
            task_id=task_id,
            previous_status=previous_status,
            new_status=new_status,
            message=message,
            payload=payload or {},
        )
        self.state = self.state.append_event(event)

    def _transition(
        self,
        task_id: str,
        target: TaskStatus,
        *,
        lease: TaskLease | None = None,
        blocker: str | None = None,
        error: str | None = None,
        failure_category: FailureCategory | None = None,
        output_artifact_ids: tuple[str, ...] | None = None,
        no_artifact_reason: str | None = None,
    ) -> None:
        current = self.state.tasks[task_id]
        updated = current.transition(
            target,
            at=self._now(),
            lease=lease,
            blocker=blocker,
            error=error,
            failure_category=failure_category,
            output_artifact_ids=output_artifact_ids,
            no_artifact_reason=no_artifact_reason,
        )
        self.state = self.state.replace_task(updated)
        self._record_event(
            WorkflowEventType.STATUS_TRANSITION,
            task_id=task_id,
            previous_status=current.status,
            new_status=target,
            message=error if error is not None else f"task entered {target.value}",
            payload={
                "failure_category": (
                    failure_category.value if failure_category is not None else None
                )
            },
        )

    def _checkpoint(self) -> None:
        at = self._now()
        usage = self.budgets.checkpoint(at=at)
        sequence = self.state.checkpoint_sequence + 1
        self.state = self.state.model_copy(
            update={
                "budget_usage": usage.model_dump(mode="json"),
                "checkpoint_sequence": sequence,
                "updated_at": at,
            }
        )
        self._record_event(
            WorkflowEventType.CHECKPOINT_SAVED,
            message="atomic workflow checkpoint",
            payload={"checkpoint_sequence": sequence},
        )
        self._atomic_write(self.checkpoint_path, canonical_json(self.state) + "\n")
        event_text = "".join(canonical_json(event) + "\n" for event in self.state.event_log.events)
        self._atomic_write(self.events_path, event_text)

    def _recover_interrupted_tasks(self) -> None:
        recovered = []
        for task_id in self.graph.task_ids:
            task = self.state.tasks[task_id]
            if task.status in {TaskStatus.LEASED, TaskStatus.RUNNING, TaskStatus.VALIDATING}:
                recovered_task = task.recover_to_ready(
                    at=self._now(), reason="recovered from an interrupted checkpoint"
                )
                self.state = self.state.replace_task(recovered_task)
                recovered.append(task_id)
        self.state = self.state.model_copy(update={"active_agents": ()})
        for task_id in recovered:
            self._record_event(
                WorkflowEventType.NOTE,
                task_id=task_id,
                message="stale active lease cleared during resume",
            )

    def _task_inputs(self, task: TaskContract) -> tuple[str, ...]:
        dependency_ids = (*task.dependencies, *task.optional_dependencies)
        return tuple(
            sorted(
                artifact_id
                for dependency in dependency_ids
                for artifact_id in self.state.tasks[dependency].output_artifact_ids
            )
        )

    def _budget_request(self, task: TaskContract) -> BudgetRequest:
        return BudgetRequest(
            tokens=task.budget.max_tokens,
            gpu_hours=task.budget.required_gpu_hours,
            training_gpu_hours=task.budget.required_gpu_hours,
        )

    def _mark_ready(self) -> None:
        for task_id in self.graph.ready_task_ids(self.state):
            if self.state.tasks[task_id].status in {TaskStatus.PENDING, TaskStatus.RETRY}:
                self._transition(task_id, TaskStatus.READY)

    def _skip_unavailable_optional_tasks(self) -> bool:
        changed = False
        for task_id in self.graph.task_ids:
            task = self.graph.task(task_id)
            state = self.state.tasks[task_id]
            if (
                state.status is TaskStatus.READY
                and task.optional
                and task.budget.required_gpu_hours > 0
            ):
                decision = self.budgets.training_decision(task.budget.required_gpu_hours)
                if not decision.should_train:
                    reason = f"optional GPU stage skipped: {decision.reason}"
                    self._transition(
                        task_id,
                        TaskStatus.CANCELLED,
                        no_artifact_reason=reason,
                    )
                    self.state = self.state.model_copy(
                        update={"decisions": (*self.state.decisions, reason)}
                    )
                    changed = True
        return changed

    def _lease_task(
        self,
        task: TaskContract,
        active_agent_ids: set[str],
    ) -> _ScheduledWork | None:
        try:
            agent = self.registry.select(
                task.owner,
                active_agent_ids,
                task_type=task.task_type,
                required_paths=task.authorized_files,
            )
            request = self._budget_request(task)
            if not self.budgets.can_start(request):
                self._block_and_escalate(
                    task.task_id,
                    "declared task budget exceeds remaining sprint budget",
                    FailureCategory.BUDGET_EXCEEDED,
                )
                return None
            path_lease = self.leases.acquire(
                task.task_id,
                task.authorized_files,
                agent_id=agent.agent_id,
                at=self._now(),
            )
        except LeaseConflictError as exc:
            self._record_event(
                WorkflowEventType.NOTE,
                task_id=task.task_id,
                message=str(exc),
                payload={"failure_category": FailureCategory.FILE_LEASE_CONFLICT.value},
            )
            return None
        except (AgentSelectionError, LeaseCapacityError):
            return None
        lease = TaskLease(
            lease_id=path_lease.lease_id,
            worker_id=agent.agent_id,
            acquired_at=path_lease.granted_at,
            expires_at=path_lease.expires_at,
            authorized_files=path_lease.paths,
        )
        self._transition(task.task_id, TaskStatus.LEASED, lease=lease)
        self._transition(task.task_id, TaskStatus.RUNNING)
        active_agent_ids.add(agent.agent_id)
        return _ScheduledWork(
            task=task,
            agent_id=agent.agent_id,
            lease=path_lease,
            input_artifact_ids=self._task_inputs(task),
            attempt=self.state.tasks[task.task_id].attempt_count,
        )

    def _execute_wave(self, work: Sequence[_ScheduledWork]) -> dict[str, WorkerResult]:
        results: dict[str, WorkerResult] = {}
        with ThreadPoolExecutor(max_workers=len(work), thread_name_prefix="abp-agent") as pool:
            futures = {}
            started = {}
            for item in work:
                future = pool.submit(
                    self.executor.run,
                    item.task,
                    input_artifact_ids=item.input_artifact_ids,
                    seed=self.definition.seed,
                    attempt=item.attempt,
                )
                futures[future] = item
                started[future] = time.monotonic()
            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # worker isolation boundary
                    result = WorkerResult(
                        task_id=item.task.task_id,
                        succeeded=False,
                        error=f"worker raised {type(exc).__name__}: {exc}",
                        failure_category=FailureCategory.MODEL_UNAVAILABLE,
                        retryable=True,
                    )
                elapsed = max(0.0, time.monotonic() - started[future])
                if elapsed > item.task.budget.max_runtime_seconds:
                    result = WorkerResult(
                        task_id=item.task.task_id,
                        succeeded=False,
                        error=(
                            f"task exceeded {item.task.budget.max_runtime_seconds}-second "
                            "wall-clock limit"
                        ),
                        failure_category=FailureCategory.BUDGET_EXCEEDED,
                        retryable=False,
                    )
                results[item.task.task_id] = result
        return results

    def _artifact_path(self, relative_path: str) -> Path:
        path = (self.output_root / relative_path).resolve()
        if not path.is_relative_to(self.output_root) or path.is_symlink():
            raise OrchestrationError(f"artifact path escapes workflow output: {relative_path}")
        return path

    def _materialize_artifacts(
        self, task: TaskContract, result: WorkerResult, *, agent_id: str
    ) -> tuple[str, ...]:
        artifact_ids = []
        for proposal in sorted(result.artifacts, key=lambda item: item.artifact_id):
            path = self._artifact_path(proposal.path)
            self._atomic_write(path, proposal.content)
            artifact = ArtifactContract(
                artifact_id=proposal.artifact_id,
                produced_by_task=task.task_id,
                produced_by_agent=agent_id,
                logical_name=proposal.logical_name,
                path=proposal.path,
                media_type=proposal.media_type,
                created_at=self._now(),
                source_commit=self.state.current_commit,
                downstream_task_ids=tuple(
                    sorted(
                        dependent.task_id
                        for dependent in self.definition.tasks
                        if task.task_id
                        in (*dependent.dependencies, *dependent.optional_dependencies)
                    )
                ),
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
                validation_status=ValidationStatus.PASSED,
                validation_notes=("worker result and acceptance checks passed",),
                metadata={"offline": True, "synthetic": True},
            )
            self.state = self.state.model_copy(
                update={"artifacts": {**self.state.artifacts, artifact.artifact_id: artifact}}
            )
            artifact_ids.append(artifact.artifact_id)
            self._record_event(
                WorkflowEventType.ARTIFACT_REGISTERED,
                task_id=task.task_id,
                message=f"registered {artifact.artifact_id}",
                payload={"sha256": artifact.sha256, "path": artifact.path},
            )
        return tuple(artifact_ids)

    def _register_handoffs(self, task: TaskContract, artifact_ids: tuple[str, ...]) -> None:
        if not artifact_ids:
            return
        handoffs = list(self.state.handoffs)
        for dependent in self.definition.tasks:
            if task.task_id not in (*dependent.dependencies, *dependent.optional_dependencies):
                continue
            handoff = HandoffContract(
                handoff_id=f"handoff-{task.task_id}-to-{dependent.task_id}",
                from_task_id=task.task_id,
                to_task_id=dependent.task_id,
                artifact_ids=artifact_ids,
                summary=f"validated outputs from {task.task_id}",
                created_at=self._now(),
                validation_status=ValidationStatus.PASSED,
                acceptance_notes=("artifact hashes and producer were registered",),
            )
            if any(existing.handoff_id == handoff.handoff_id for existing in handoffs):
                continue
            handoffs.append(handoff)
            self._record_event(
                WorkflowEventType.HANDOFF_REGISTERED,
                task_id=task.task_id,
                message=f"handoff to {dependent.task_id}",
            )
        self.state = self.state.model_copy(update={"handoffs": tuple(handoffs)})

    def _result_failure(
        self,
        task: TaskContract,
        validation: ResultValidation,
    ) -> None:
        error = "; ".join(validation.failures)
        category = validation.failure_category or FailureCategory.VALIDATION_FAILURE
        task_state = self.state.tasks[task.task_id]
        can_retry = validation.retryable and task_state.attempt_count < task.budget.max_attempts
        if can_retry:
            self._transition(
                task.task_id,
                TaskStatus.RETRY,
                error=error,
                failure_category=category,
            )
        else:
            self._block_and_escalate(task.task_id, error, category)

    def _block_and_escalate(self, task_id: str, error: str, category: FailureCategory) -> None:
        self._transition(
            task_id,
            TaskStatus.BLOCKED,
            blocker=error,
            error=error,
            failure_category=category,
        )
        self._transition(
            task_id,
            TaskStatus.ESCALATED,
            error=error,
            failure_category=category,
        )
        self.state = self.state.model_copy(
            update={"blockers": (*self.state.blockers, f"{task_id}: {error}")}
        )

    def _apply_result(self, item: _ScheduledWork, result: WorkerResult) -> None:
        task = item.task
        self._transition(task.task_id, TaskStatus.VALIDATING)
        gate = self.gates_by_task.get(task.task_id)
        validation = validate_worker_result(task, result, gate=gate)
        if validation.passed:
            try:
                self.budgets.charge(
                    tokens=result.tokens_used,
                    gpu_hours=result.gpu_hours_used,
                    training_gpu_hours=(
                        result.gpu_hours_used if task.budget.required_gpu_hours > 0 else 0
                    ),
                    at=self._now(),
                )
            except BudgetExceededError as exc:
                validation = ResultValidation(
                    passed=False,
                    checks=validation.checks,
                    failures=(str(exc),),
                    failure_category=FailureCategory.BUDGET_EXCEEDED,
                    retryable=False,
                )
        if validation.passed:
            artifact_ids = self._materialize_artifacts(task, result, agent_id=item.agent_id)
            self._transition(
                task.task_id,
                TaskStatus.COMPLETED,
                output_artifact_ids=artifact_ids,
                no_artifact_reason=result.no_artifact_reason,
            )
            if gate is not None:
                self.state = self.state.model_copy(
                    update={"gates": {**self.state.gates, gate.gate_id: True}}
                )
            self._register_handoffs(task, artifact_ids)
            release_result: ReleaseResult = "completed"
        else:
            self._result_failure(task, validation)
            release_result = "failed"
        self.leases.release(
            item.lease.lease_id,
            agent_id=item.agent_id,
            result=release_result,
            at=self._now(),
        )

    def _propagate_dependency_failures(self) -> bool:
        changed = False
        failed = {TaskStatus.BLOCKED, TaskStatus.ESCALATED, TaskStatus.CANCELLED}
        for task_id in self.graph.task_ids:
            state = self.state.tasks[task_id]
            if state.status not in {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RETRY}:
                continue
            task = self.graph.task(task_id)
            failed_required = [
                dependency
                for dependency in task.dependencies
                if self.state.tasks[dependency].status in failed
            ]
            if failed_required:
                error = "required dependency did not complete: " + ", ".join(failed_required)
                self._block_and_escalate(task_id, error, FailureCategory.DEPENDENCY_MISSING)
                changed = True
        return changed

    def _is_terminal(self) -> bool:
        terminal = {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ESCALATED}
        return all(task.status in terminal for task in self.state.tasks.values())

    def _semantic_state(self) -> dict[str, object]:
        return {
            "artifacts": {
                artifact_id: {
                    "path": artifact.path,
                    "producer": artifact.produced_by_task,
                    "sha256": artifact.sha256,
                    "size_bytes": artifact.size_bytes,
                }
                for artifact_id, artifact in sorted(self.state.artifacts.items())
            },
            "decisions": list(self.state.decisions),
            "gates": dict(sorted(self.state.gates.items())),
            "seed": self.definition.seed,
            "tasks": {
                task_id: {
                    "attempt_count": task.attempt_count,
                    "no_artifact_reason": task.no_artifact_reason,
                    "output_artifact_ids": list(task.output_artifact_ids),
                    "retry_count": task.retry_count,
                    "status": task.status.value,
                }
                for task_id, task in sorted(self.state.tasks.items())
            },
            "workflow_id": self.state.workflow_id,
        }

    def summary(self, status: Literal["completed", "paused", "failed"]) -> WorkflowRunSummary:
        statuses = [task.status for task in self.state.tasks.values()]
        return WorkflowRunSummary(
            workflow_id=self.state.workflow_id,
            status=status,
            state_sha256=sha256_value(self._semantic_state()),
            completed_tasks=statuses.count(TaskStatus.COMPLETED),
            cancelled_tasks=statuses.count(TaskStatus.CANCELLED),
            escalated_tasks=statuses.count(TaskStatus.ESCALATED),
            checkpoint_sequence=self.state.checkpoint_sequence,
        )

    def _write_summary(self, summary: WorkflowRunSummary) -> None:
        self._atomic_write(
            self.output_root / "workflow-summary.json", canonical_json(summary) + "\n"
        )

    def run(self, *, max_waves: int | None = None) -> WorkflowRunSummary:
        """Advance ready work in bounded waves until terminal or deliberately paused."""

        waves = 0
        while not self._is_terminal():
            if max_waves is not None and waves >= max_waves:
                summary = self.summary("paused")
                self._write_summary(summary)
                return summary
            self._mark_ready()
            changed = self._skip_unavailable_optional_tasks()
            ready_ids = [
                task_id
                for task_id in self.graph.task_ids
                if self.state.tasks[task_id].status is TaskStatus.READY
            ]
            active_agent_ids: set[str] = set()
            work: list[_ScheduledWork] = []
            for task_id in ready_ids:
                if len(work) >= min(self.definition.max_workers, self.registry.max_workers):
                    break
                scheduled = self._lease_task(self.graph.task(task_id), active_agent_ids)
                if scheduled is not None:
                    work.append(scheduled)
            if not work:
                if self._propagate_dependency_failures() or changed:
                    self._checkpoint()
                    continue
                raise OrchestrationError("workflow made no progress; inspect leases and agents")
            self.state = self.state.model_copy(
                update={"active_agents": tuple(sorted(active_agent_ids)), "phase": "executing"}
            )
            self._checkpoint()
            results = self._execute_wave(work)
            for item in sorted(work, key=lambda candidate: candidate.task.task_id):
                self._apply_result(item, results[item.task.task_id])
            self.state = self.state.model_copy(update={"active_agents": (), "phase": "integrating"})
            self._checkpoint()
            waves += 1

        final = self.state.tasks[self.definition.final_task_id]
        mandatory_incomplete = [
            task.task_id
            for task in self.definition.tasks
            if not task.optional
            and self.state.tasks[task.task_id].status is not TaskStatus.COMPLETED
        ]
        all_gates_passed = all(self.state.gates.values())
        completed = (
            final.status is TaskStatus.COMPLETED and not mandatory_incomplete and all_gates_passed
        )
        self.state = self.state.model_copy(update={"phase": "completed" if completed else "failed"})
        self._checkpoint()
        summary = self.summary("completed" if completed else "failed")
        self._write_summary(summary)
        return summary
