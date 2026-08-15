"""Atomic wall-clock, token, GPU, retry, and optional-training budgets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.orchestration.contracts import OrchestrationModel


class BudgetError(RuntimeError):
    """Base error for budget configuration and accounting failures."""


class BudgetConfigurationError(BudgetError):
    """A budget request is malformed or internally inconsistent."""


class BudgetExceededError(BudgetError):
    """A charge or task reservation would exceed a configured limit."""

    def __init__(self, exceeded: tuple[str, ...]) -> None:
        self.exceeded = exceeded
        super().__init__(f"budget exceeded: {', '.join(exceeded)}")


class BudgetLimits(OrchestrationModel):
    """Supervisor limits; ``None`` means an optional meter is unbounded."""

    max_wall_clock_seconds: float = Field(ge=0)
    max_tokens: int | None = Field(default=None, ge=0)
    max_gpu_hours: float | None = Field(default=None, ge=0)
    max_training_gpu_hours: float = Field(default=0, ge=0)
    max_automatic_retries: int = Field(default=2, ge=0, le=2)
    max_malformed_output_retries: int = Field(default=1, ge=0, le=2)
    deadline: datetime | None = None

    @model_validator(mode="after")
    def validate_limits(self) -> BudgetLimits:
        if self.max_gpu_hours is not None and self.max_training_gpu_hours > self.max_gpu_hours:
            raise ValueError("training GPU budget cannot exceed total GPU budget")
        if self.deadline is not None and (
            self.deadline.tzinfo is None or self.deadline.utcoffset() is None
        ):
            raise ValueError("deadline must be timezone-aware")
        return self


class BudgetUsage(OrchestrationModel):
    """Cumulative, monotonic usage counters."""

    wall_clock_seconds: float = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    gpu_hours: float = Field(default=0, ge=0)
    training_gpu_hours: float = Field(default=0, ge=0)
    automatic_retries: int = Field(default=0, ge=0)
    malformed_output_retries: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_gpu_usage(self) -> BudgetUsage:
        if self.training_gpu_hours > self.gpu_hours:
            raise ValueError("training GPU usage cannot exceed total GPU usage")
        return self


class BudgetRequest(OrchestrationModel):
    """Expected incremental cost of starting a task or operation."""

    wall_clock_seconds: float = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    gpu_hours: float = Field(default=0, ge=0)
    training_gpu_hours: float = Field(default=0, ge=0)
    automatic_retries: int = Field(default=0, ge=0)
    malformed_output_retries: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_gpu_request(self) -> BudgetRequest:
        if self.training_gpu_hours > self.gpu_hours:
            raise ValueError("training GPU request cannot exceed total GPU request")
        return self


class BudgetRemaining(OrchestrationModel):
    wall_clock_seconds: float
    tokens: int | None
    gpu_hours: float | None
    training_gpu_hours: float
    automatic_retries: int
    malformed_output_retries: int


TrainingDecisionReason = Literal[
    "approved",
    "not_required",
    "deadline_exceeded",
    "wall_clock_budget_unavailable",
    "training_budget_unavailable",
    "gpu_budget_unavailable",
]


class TrainingBudgetDecision(OrchestrationModel):
    """A first-class skip/execute decision for the optional training graph branch."""

    should_train: bool
    required_gpu_hours: float = Field(ge=0)
    remaining_training_gpu_hours: float = Field(ge=0)
    remaining_total_gpu_hours: float | None = Field(default=None, ge=0)
    reason: TrainingDecisionReason

    @property
    def allowed(self) -> bool:
        return self.should_train


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BudgetConfigurationError(f"{field_name} must be numeric")
    number = float(value)
    if number < 0:
        raise BudgetConfigurationError(f"{field_name} cannot be negative")
    return number


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BudgetConfigurationError(f"{field_name} must be an integer")
    if value < 0:
        raise BudgetConfigurationError(f"{field_name} cannot be negative")
    return value


def _task_value(task: object, names: tuple[str, ...], default: object) -> object:
    if isinstance(task, Mapping):
        for name in names:
            if name in task:
                return task[name]
        return default
    for name in names:
        if hasattr(task, name):
            return getattr(task, name)
    return default


def _request_from_task(task: object) -> BudgetRequest:
    if isinstance(task, BudgetRequest):
        return task
    wall_clock = _number(
        _task_value(task, ("wall_clock_seconds", "timebox_seconds"), 0),
        "wall_clock_seconds",
    )
    raw_tokens = _task_value(task, ("tokens", "token_budget"), 0)
    tokens = 0 if raw_tokens is None else _integer(raw_tokens, "tokens")
    raw_gpu_hours = _task_value(task, ("gpu_hours", "gpu_hour_budget"), 0)
    gpu_hours = 0.0 if raw_gpu_hours is None else _number(raw_gpu_hours, "gpu_hours")
    raw_training_gpu_hours = _task_value(
        task, ("training_gpu_hours", "training_gpu_hour_budget"), 0
    )
    training_gpu_hours = (
        0.0
        if raw_training_gpu_hours is None
        else _number(raw_training_gpu_hours, "training_gpu_hours")
    )
    automatic_retries = _integer(
        _task_value(task, ("automatic_retries", "retry_cost"), 0),
        "automatic_retries",
    )
    malformed_retries = _integer(
        _task_value(task, ("malformed_output_retries",), 0),
        "malformed_output_retries",
    )
    try:
        return BudgetRequest(
            wall_clock_seconds=wall_clock,
            tokens=tokens,
            gpu_hours=gpu_hours,
            training_gpu_hours=training_gpu_hours,
            automatic_retries=automatic_retries,
            malformed_output_retries=malformed_retries,
        )
    except ValueError as exc:
        raise BudgetConfigurationError(f"invalid task budget: {exc}") from exc


class BudgetAccount:
    """Atomic budget ledger for the supervisor's sprint and task admission checks."""

    def __init__(
        self,
        limits: BudgetLimits,
        *,
        usage: BudgetUsage | None = None,
        started_at: datetime | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.limits = limits
        self._usage = usage or BudgetUsage()
        self._clock = clock
        self._started_at = self._aware_utc(started_at or clock())
        self._assert_within_limits(self._usage)

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise BudgetConfigurationError("budget timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @property
    def usage(self) -> BudgetUsage:
        return self._usage

    @property
    def deadline(self) -> datetime | None:
        return self.limits.deadline

    @property
    def max_retries(self) -> int:
        return self.limits.max_automatic_retries

    def _observed_usage(self, at: datetime | None = None) -> BudgetUsage:
        now = self._aware_utc(at or self._clock())
        elapsed = max(0.0, (now - self._started_at).total_seconds())
        if elapsed <= self._usage.wall_clock_seconds:
            return self._usage
        return self._usage.model_copy(update={"wall_clock_seconds": elapsed})

    def checkpoint(self, *, at: datetime | None = None) -> BudgetUsage:
        """Materialize observed wall-clock time into the persisted usage snapshot."""

        observed = self._observed_usage(at)
        self._assert_within_limits(observed)
        self._usage = observed
        return observed

    def remaining(self, *, at: datetime | None = None) -> BudgetRemaining:
        usage = self._observed_usage(at)
        limits = self.limits
        return BudgetRemaining(
            wall_clock_seconds=max(0.0, limits.max_wall_clock_seconds - usage.wall_clock_seconds),
            tokens=None if limits.max_tokens is None else max(0, limits.max_tokens - usage.tokens),
            gpu_hours=(
                None
                if limits.max_gpu_hours is None
                else max(0.0, limits.max_gpu_hours - usage.gpu_hours)
            ),
            training_gpu_hours=max(0.0, limits.max_training_gpu_hours - usage.training_gpu_hours),
            automatic_retries=max(0, limits.max_automatic_retries - usage.automatic_retries),
            malformed_output_retries=max(
                0,
                limits.max_malformed_output_retries - usage.malformed_output_retries,
            ),
        )

    def _exceeded(self, usage: BudgetUsage, *, at: datetime | None = None) -> tuple[str, ...]:
        exceeded = []
        if usage.wall_clock_seconds > self.limits.max_wall_clock_seconds:
            exceeded.append("wall_clock_seconds")
        if self.limits.max_tokens is not None and usage.tokens > self.limits.max_tokens:
            exceeded.append("tokens")
        if self.limits.max_gpu_hours is not None and usage.gpu_hours > self.limits.max_gpu_hours:
            exceeded.append("gpu_hours")
        if usage.training_gpu_hours > self.limits.max_training_gpu_hours:
            exceeded.append("training_gpu_hours")
        if usage.automatic_retries > self.limits.max_automatic_retries:
            exceeded.append("automatic_retries")
        if usage.malformed_output_retries > self.limits.max_malformed_output_retries:
            exceeded.append("malformed_output_retries")
        now = self._aware_utc(at or self._clock())
        if self.limits.deadline is not None and now > self.limits.deadline.astimezone(UTC):
            exceeded.append("deadline")
        return tuple(exceeded)

    def _assert_within_limits(self, usage: BudgetUsage, *, at: datetime | None = None) -> None:
        exceeded = self._exceeded(usage, at=at)
        if exceeded:
            raise BudgetExceededError(exceeded)

    def _project(self, request: BudgetRequest, *, at: datetime | None = None) -> BudgetUsage:
        current = self._observed_usage(at)
        return BudgetUsage(
            wall_clock_seconds=current.wall_clock_seconds + request.wall_clock_seconds,
            tokens=current.tokens + request.tokens,
            gpu_hours=current.gpu_hours + request.gpu_hours,
            training_gpu_hours=current.training_gpu_hours + request.training_gpu_hours,
            automatic_retries=current.automatic_retries + request.automatic_retries,
            malformed_output_retries=(
                current.malformed_output_retries + request.malformed_output_retries
            ),
        )

    def can_start(self, task: object, *, at: datetime | None = None) -> bool:
        """Return whether a task's declared reservation fits without mutating usage."""

        request = _request_from_task(task)
        projected = self._project(request, at=at)
        return not self._exceeded(projected, at=at)

    def require_start(self, task: object, *, at: datetime | None = None) -> BudgetRequest:
        """Validate admission and return the normalized request for event recording."""

        request = _request_from_task(task)
        self._assert_within_limits(self._project(request, at=at), at=at)
        return request

    def charge(
        self,
        request: BudgetRequest | None = None,
        *,
        wall_clock_seconds: float = 0,
        tokens: int = 0,
        gpu_hours: float = 0,
        training_gpu_hours: float = 0,
        automatic_retries: int = 0,
        malformed_output_retries: int = 0,
        at: datetime | None = None,
    ) -> BudgetUsage:
        """Atomically apply usage; a rejected charge never partially updates state."""

        if request is not None and any(
            value != 0
            for value in (
                wall_clock_seconds,
                tokens,
                gpu_hours,
                training_gpu_hours,
                automatic_retries,
                malformed_output_retries,
            )
        ):
            raise BudgetConfigurationError(
                "pass either a BudgetRequest or individual charge fields, not both"
            )
        if request is None:
            try:
                request = BudgetRequest(
                    wall_clock_seconds=wall_clock_seconds,
                    tokens=tokens,
                    gpu_hours=gpu_hours,
                    training_gpu_hours=training_gpu_hours,
                    automatic_retries=automatic_retries,
                    malformed_output_retries=malformed_output_retries,
                )
            except ValueError as exc:
                raise BudgetConfigurationError(f"invalid budget charge: {exc}") from exc
        projected = self._project(request, at=at)
        self._assert_within_limits(projected, at=at)
        self._usage = projected
        return projected

    def training_decision(
        self,
        required_gpu_hours: float,
        *,
        at: datetime | None = None,
    ) -> TrainingBudgetDecision:
        """Decide the optional training edge without turning a skip into a failure."""

        required = _number(required_gpu_hours, "required_gpu_hours")
        now = self._aware_utc(at or self._clock())
        remaining = self.remaining(at=now)
        if required == 0:
            return TrainingBudgetDecision(
                should_train=False,
                required_gpu_hours=required,
                remaining_training_gpu_hours=remaining.training_gpu_hours,
                remaining_total_gpu_hours=remaining.gpu_hours,
                reason="not_required",
            )
        if self.limits.deadline is not None and now > self.limits.deadline.astimezone(UTC):
            reason: TrainingDecisionReason = "deadline_exceeded"
        elif remaining.wall_clock_seconds <= 0:
            reason = "wall_clock_budget_unavailable"
        elif required > remaining.training_gpu_hours:
            reason = "training_budget_unavailable"
        elif remaining.gpu_hours is not None and required > remaining.gpu_hours:
            reason = "gpu_budget_unavailable"
        else:
            reason = "approved"
        return TrainingBudgetDecision(
            should_train=reason == "approved",
            required_gpu_hours=required,
            remaining_training_gpu_hours=remaining.training_gpu_hours,
            remaining_total_gpu_hours=remaining.gpu_hours,
            reason=reason,
        )
