"""Pre-action call, token, monetary, and time budgets for an authorized pilot."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from affective_belief_persistence.gate3.contracts import Gate3Budget


class PilotBudgetExceededError(RuntimeError):
    """A transport reservation would exceed an authorized Gate 3 limit."""


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class LivePilotBudgetAccount:
    """Reserve worst-case usage before transport and settle without overrun."""

    def __init__(
        self,
        budget: Gate3Budget,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.budget = budget
        self.clock = clock
        self.started_at = clock()
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.estimated_cost_usd = 0.0
        self._next_id = 1
        self._open: dict[int, BudgetReservation] = {}

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, self.clock() - self.started_at)

    def _check_time(self) -> None:
        if self.elapsed_seconds >= self.budget.max_wall_clock_seconds:
            raise PilotBudgetExceededError("Gate 3 wall-clock budget exhausted")

    def reserve_call(
        self,
        *,
        input_tokens: int,
        max_output_tokens: int,
        max_estimated_cost_usd: float,
    ) -> BudgetReservation:
        """Reserve worst-case usage before any live transport invocation."""

        if input_tokens < 0 or max_output_tokens < 0 or max_estimated_cost_usd < 0:
            raise ValueError("Gate 3 reservation values cannot be negative")
        self._check_time()
        projected = (
            self.calls + 1,
            self.input_tokens + input_tokens,
            self.output_tokens + max_output_tokens,
            self.estimated_cost_usd + max_estimated_cost_usd,
        )
        limits = (
            self.budget.max_model_calls,
            self.budget.max_input_tokens,
            self.budget.max_output_tokens,
            self.budget.max_estimated_cost_usd,
        )
        labels = ("model-call", "input-token", "output-token", "monetary")
        for value, limit, label in zip(projected, limits, labels, strict=True):
            if value > limit:
                raise PilotBudgetExceededError(f"Gate 3 {label} budget would be exceeded")
        reservation = BudgetReservation(
            reservation_id=self._next_id,
            input_tokens=input_tokens,
            output_tokens=max_output_tokens,
            estimated_cost_usd=max_estimated_cost_usd,
        )
        self._next_id += 1
        self.calls, self.input_tokens, self.output_tokens, self.estimated_cost_usd = projected
        self._open[reservation.reservation_id] = reservation
        return reservation

    def settle_call(
        self,
        reservation: BudgetReservation,
        *,
        actual_input_tokens: int,
        actual_output_tokens: int,
        actual_cost_usd: float,
    ) -> None:
        """Replace the reservation with actual usage without accepting overrun."""

        current = self._open.get(reservation.reservation_id)
        if current != reservation:
            raise ValueError("Gate 3 reservation is unknown or already settled")
        actual = (actual_input_tokens, actual_output_tokens, actual_cost_usd)
        reserved = (
            reservation.input_tokens,
            reservation.output_tokens,
            reservation.estimated_cost_usd,
        )
        if any(value < 0 for value in actual):
            raise ValueError("actual Gate 3 usage cannot be negative")
        if any(value > limit for value, limit in zip(actual, reserved, strict=True)):
            raise PilotBudgetExceededError("provider usage exceeded its pre-action reservation")
        self.input_tokens += actual_input_tokens - reservation.input_tokens
        self.output_tokens += actual_output_tokens - reservation.output_tokens
        self.estimated_cost_usd += actual_cost_usd - reservation.estimated_cost_usd
        del self._open[reservation.reservation_id]

    def assert_settled(self) -> None:
        self._check_time()
        if self._open:
            raise PilotBudgetExceededError("Gate 3 has unsettled provider reservations")
