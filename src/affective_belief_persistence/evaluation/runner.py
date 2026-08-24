"""Resumable, idempotent, budgeted offline execution for Issue #14 plans."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from enum import StrEnum
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.evaluation.config import EvaluationBudget
from affective_belief_persistence.evaluation.matrix import (
    ExperimentAssignment,
    ExperimentMatrix,
)
from affective_belief_persistence.harness.contracts import Sha256


class EvaluationRunnerError(RuntimeError):
    """Offline evaluation cannot proceed without violating a run invariant."""


class BudgetExceededError(EvaluationRunnerError):
    """A hard trajectory, model-call, or wall-clock budget is exhausted."""


class OfflineExecutionError(EvaluationRunnerError):
    """An executor attempted a provider call while live calls were disabled."""


class RawResultError(EvaluationRunnerError):
    """An immutable raw result is missing, corrupt, unsafe, or inconsistent."""


class ResultStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"


class RunnerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RawResultPointer(RunnerModel):
    """Content-addressed reference to an immutable raw trajectory artifact."""

    relative_path: str = Field(min_length=1)
    sha256: Sha256
    size_bytes: int = Field(ge=1)
    media_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relative_path(self) -> RawResultPointer:
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts or path.name in {"", "."}:
            raise ValueError("raw-result pointer must be a safe relative POSIX path")
        if path.parts[-2:] != (self.sha256[:2], f"{self.sha256}.json"):
            raise ValueError("raw-result pointer path must be content addressed")
        return self


class OfflineExecutionOutcome(RunnerModel):
    """Executor output that preserves invalid bytes and distinguishes missing output."""

    status: ResultStatus
    raw_payload: bytes | None = None
    failure_reason: str | None = Field(default=None, min_length=1)
    media_type: Literal["application/json"] = "application/json"

    @model_validator(mode="after")
    def validate_outcome(self) -> OfflineExecutionOutcome:
        has_raw = self.raw_payload is not None and len(self.raw_payload) > 0
        if self.status is ResultStatus.VALID and (not has_raw or self.failure_reason is not None):
            raise ValueError("valid outcomes require raw bytes and no failure reason")
        if self.status is ResultStatus.INVALID and (not has_raw or self.failure_reason is None):
            raise ValueError("invalid outcomes require preserved raw bytes and a reason")
        if self.status is ResultStatus.MISSING and (has_raw or self.failure_reason is None):
            raise ValueError("missing outcomes require a reason and no invented raw bytes")
        return self


class TrajectoryResult(RunnerModel):
    """Hash-bound terminal result for exactly one matrix assignment."""

    schema_version: Literal["1.0"] = "1.0"
    run_id: Sha256
    matrix_sha256: Sha256
    status: ResultStatus
    raw_result: RawResultPointer | None
    failure_reason: str | None = Field(default=None, min_length=1)
    model_calls: Literal[0] = 0
    elapsed_seconds: float = Field(ge=0)
    result_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"result_sha256"})

    @model_validator(mode="after")
    def validate_result(self) -> TrajectoryResult:
        has_pointer = self.raw_result is not None
        if self.status is ResultStatus.VALID and (
            not has_pointer or self.failure_reason is not None
        ):
            raise ValueError("valid result must point to raw output and have no failure reason")
        if self.status is ResultStatus.INVALID and (not has_pointer or self.failure_reason is None):
            raise ValueError("invalid result must preserve raw output and its reason")
        if self.status is ResultStatus.MISSING and (has_pointer or self.failure_reason is None):
            raise ValueError("missing result must not fabricate a raw-output pointer")
        if self.result_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("trajectory result hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> TrajectoryResult:
        payload = {**values, "result_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["result_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


class ImmutableRawResultStore:
    """Write-once content-addressed storage; existing bytes are never overwritten."""

    def __init__(self, root: Path, *, project_root: Path) -> None:
        repository = project_root.resolve()
        resolved = root.resolve()
        allowed = (repository / "runs/local").resolve()
        if not resolved.is_relative_to(allowed) or root.is_symlink():
            raise RawResultError("raw-result store must be a non-symlink under runs/local")
        self.root = resolved

    def _path(self, digest: str) -> Path:
        return self.root / digest[:2] / f"{digest}.json"

    def put(self, payload: bytes, *, media_type: str = "application/json") -> RawResultPointer:
        if not payload:
            raise RawResultError("raw results cannot be empty")
        digest = sha256(payload).hexdigest()
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink() or path.is_symlink():
            raise RawResultError("raw-result path cannot traverse a symlink")
        if path.exists():
            try:
                existing = path.read_bytes()
            except OSError as exc:
                raise RawResultError(f"cannot verify immutable raw result {path}: {exc}") from exc
            if existing != payload:
                raise RawResultError("content-addressed raw-result path contains different bytes")
        else:
            try:
                with path.open("xb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError:
                if path.is_symlink() or path.read_bytes() != payload:
                    raise RawResultError(
                        "concurrent immutable raw-result write disagreed"
                    ) from None
            except OSError as exc:
                raise RawResultError(f"cannot write immutable raw result {path}: {exc}") from exc
        relative = path.relative_to(self.root).as_posix()
        return RawResultPointer(
            relative_path=relative,
            sha256=digest,
            size_bytes=len(payload),
            media_type=media_type,
        )

    def verify(self, pointer: RawResultPointer) -> Path:
        candidate = self.root / pointer.relative_path
        path = candidate.resolve()
        if not path.is_relative_to(self.root) or candidate.is_symlink() or not path.is_file():
            raise RawResultError("raw-result pointer does not resolve to a regular stored file")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise RawResultError(f"cannot read raw result {path}: {exc}") from exc
        digest = sha256(payload).hexdigest()
        if digest != pointer.sha256 or len(payload) != pointer.size_bytes:
            raise RawResultError("raw-result pointer failed size or content verification")
        return path


class HardBudgetAccount:
    """Pre-action accounting for hard trajectory, provider-call, and time limits."""

    def __init__(
        self,
        limits: EvaluationBudget,
        *,
        live_calls_enabled: bool,
        trajectories_started: int = 0,
        model_calls: int = 0,
        elapsed_seconds: float = 0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if trajectories_started < 0 or model_calls < 0 or elapsed_seconds < 0:
            raise ValueError("budget usage cannot be negative")
        if trajectories_started > limits.max_trajectories:
            raise BudgetExceededError("trajectory budget already exceeded")
        if model_calls > limits.max_model_calls:
            raise BudgetExceededError("model-call budget already exceeded")
        if elapsed_seconds > limits.max_wall_clock_seconds:
            raise BudgetExceededError("wall-clock budget already exceeded")
        self.limits = limits
        self.live_calls_enabled = live_calls_enabled
        self.trajectories_started = trajectories_started
        self.model_calls = model_calls
        self.previous_elapsed_seconds = elapsed_seconds
        self.clock = clock
        self.started_at = clock()

    @property
    def elapsed_seconds(self) -> float:
        return self.previous_elapsed_seconds + max(0.0, self.clock() - self.started_at)

    def check_time(self) -> None:
        if self.elapsed_seconds >= self.limits.max_wall_clock_seconds:
            raise BudgetExceededError("wall-clock budget exhausted")

    def start_trajectory(self) -> None:
        self.check_time()
        if self.trajectories_started >= self.limits.max_trajectories:
            raise BudgetExceededError("trajectory budget exhausted")
        self.trajectories_started += 1

    def record_model_call(self) -> None:
        """Reserve a call before transport; offline accounts always reject it."""

        self.check_time()
        if not self.live_calls_enabled:
            raise OfflineExecutionError("live model calls are disabled for Issue #14 offline work")
        if self.model_calls >= self.limits.max_model_calls:
            raise BudgetExceededError("model-call budget exhausted")
        self.model_calls += 1


class OfflineExecutionContext:
    """The only runner-supplied route for checking time or declaring a model call."""

    def __init__(self, account: HardBudgetAccount) -> None:
        self._account = account

    def check_time(self) -> None:
        self._account.check_time()

    def record_model_call(self) -> None:
        self._account.record_model_call()


class OfflineTrajectoryExecutor(Protocol):
    def __call__(
        self,
        assignment: ExperimentAssignment,
        context: OfflineExecutionContext,
    ) -> OfflineExecutionOutcome:
        """Execute one deterministic fixture/harness trajectory without provider access."""


class EvaluationProgress(RunnerModel):
    schema_version: Literal["1.0"] = "1.0"
    matrix_sha256: Sha256
    status: Literal["complete", "paused", "budget_exhausted"]
    results: tuple[TrajectoryResult, ...]
    pending_run_ids: tuple[Sha256, ...]
    trajectories_started: int = Field(ge=0)
    model_calls: Literal[0] = 0
    elapsed_seconds: float = Field(ge=0)


class OfflineEvaluationRunner:
    """Execute or resume a matrix without duplicating any terminal assignment."""

    def __init__(
        self,
        matrix: ExperimentMatrix,
        *,
        budget: EvaluationBudget,
        raw_store: ImmutableRawResultStore,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if budget.max_trajectories != matrix.expected_trajectories:
            raise EvaluationRunnerError("runner budget does not match the matrix trajectory count")
        self.matrix = matrix
        self.budget = budget
        self.raw_store = raw_store
        self.clock = clock

    def _prior_by_id(
        self, prior_results: tuple[TrajectoryResult, ...]
    ) -> dict[str, TrajectoryResult]:
        by_id: dict[str, TrajectoryResult] = {}
        assignments = {item.run_id for item in self.matrix.assignments}
        for result in prior_results:
            if result.run_id in by_id:
                raise EvaluationRunnerError("resume state contains duplicate trajectory results")
            if (
                result.run_id not in assignments
                or result.matrix_sha256 != self.matrix.matrix_sha256
            ):
                raise EvaluationRunnerError("resume result does not belong to this matrix")
            if result.raw_result is not None:
                self.raw_store.verify(result.raw_result)
            by_id[result.run_id] = result
        return by_id

    def schedule(
        self,
        *,
        prior_results: tuple[TrajectoryResult, ...] = (),
        max_new_results: int | None = None,
    ) -> tuple[ExperimentAssignment, ...]:
        """Return only unobserved assignments, preserving deterministic matrix order."""

        if max_new_results is not None and max_new_results < 0:
            raise ValueError("max_new_results cannot be negative")
        completed = self._prior_by_id(prior_results)
        pending = tuple(item for item in self.matrix.assignments if item.run_id not in completed)
        return pending if max_new_results is None else pending[:max_new_results]

    def run(
        self,
        executor: OfflineTrajectoryExecutor,
        *,
        prior_results: tuple[TrajectoryResult, ...] = (),
        max_new_results: int | None = None,
    ) -> EvaluationProgress:
        """Run a bounded slice; terminal prior results are verified and never executed again."""

        prior = self._prior_by_id(prior_results)
        prior_elapsed = sum(item.elapsed_seconds for item in prior.values())
        account = HardBudgetAccount(
            self.budget,
            live_calls_enabled=False,
            trajectories_started=len(prior),
            model_calls=0,
            elapsed_seconds=prior_elapsed,
            clock=self.clock,
        )
        scheduled = self.schedule(
            prior_results=prior_results,
            max_new_results=max_new_results,
        )
        added: dict[str, TrajectoryResult] = {}
        budget_exhausted = False
        for assignment in scheduled:
            try:
                account.start_trajectory()
            except BudgetExceededError:
                budget_exhausted = True
                break
            started = self.clock()
            try:
                outcome = executor(assignment, OfflineExecutionContext(account))
            except OfflineExecutionError:
                raise
            except BudgetExceededError as exc:
                outcome = OfflineExecutionOutcome(
                    status=ResultStatus.MISSING,
                    failure_reason=str(exc),
                )
                budget_exhausted = True
            except Exception as exc:  # Explicit infrastructure missingness; never fabricate output.
                outcome = OfflineExecutionOutcome(
                    status=ResultStatus.MISSING,
                    failure_reason=f"executor_error:{type(exc).__name__}",
                )
            elapsed = max(0.0, self.clock() - started)
            pointer = (
                self.raw_store.put(outcome.raw_payload, media_type=outcome.media_type)
                if outcome.raw_payload is not None
                else None
            )
            added[assignment.run_id] = TrajectoryResult.create(
                run_id=assignment.run_id,
                matrix_sha256=self.matrix.matrix_sha256,
                status=outcome.status,
                raw_result=pointer,
                failure_reason=outcome.failure_reason,
                model_calls=0,
                elapsed_seconds=elapsed,
            )
            if budget_exhausted:
                break
            try:
                account.check_time()
            except BudgetExceededError:
                budget_exhausted = True
                break

        combined = {**prior, **added}
        ordered = tuple(
            combined[item.run_id] for item in self.matrix.assignments if item.run_id in combined
        )
        pending = tuple(
            item.run_id for item in self.matrix.assignments if item.run_id not in combined
        )
        if not pending:
            status: Literal["complete", "paused", "budget_exhausted"] = "complete"
        elif budget_exhausted:
            status = "budget_exhausted"
        else:
            status = "paused"
        return EvaluationProgress(
            matrix_sha256=self.matrix.matrix_sha256,
            status=status,
            results=ordered,
            pending_run_ids=pending,
            trajectories_started=account.trajectories_started,
            model_calls=0,
            elapsed_seconds=account.elapsed_seconds,
        )
