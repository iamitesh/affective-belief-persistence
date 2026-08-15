"""Immutable, exact-once resource accounting for simulated actions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value

DAILY_ACTION_POINTS = 10


class ResourceError(ValueError):
    """A debit would violate a resource invariant."""


class ResourceDebit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    debit_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_id: str = Field(min_length=1)
    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_id: str = Field(min_length=1)
    amount: int = Field(gt=0)


class DailyResourceLedger(BaseModel):
    """One day's non-carrying action-point account."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    day: int = Field(ge=1, le=40)
    budget_id: str = Field(min_length=1)
    total: int = Field(default=DAILY_ACTION_POINTS, gt=0)
    remaining: int = Field(default=DAILY_ACTION_POINTS, ge=0)
    debits: tuple[ResourceDebit, ...] = ()

    @model_validator(mode="after")
    def validate_balance(self) -> DailyResourceLedger:
        debit_ids = [item.debit_id for item in self.debits]
        event_ids = [item.event_id for item in self.debits]
        decision_ids = [item.decision_id for item in self.debits]
        if len(debit_ids) != len(set(debit_ids)):
            raise ValueError("resource debit IDs must be unique")
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("an event may debit a daily ledger only once")
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("a decision may debit a daily ledger only once")
        if self.remaining != self.total - sum(item.amount for item in self.debits):
            raise ValueError("remaining resources do not match the immutable debit ledger")
        return self

    def debit(
        self,
        *,
        event_id: str,
        decision_id: str,
        action_id: str,
        amount: int,
    ) -> DailyResourceLedger:
        """Return a new ledger after one exact-once debit."""

        if amount <= 0:
            raise ResourceError("action debit must be positive")
        if any(item.event_id == event_id for item in self.debits):
            raise ResourceError(f"event has already been debited: {event_id}")
        if any(item.decision_id == decision_id for item in self.debits):
            raise ResourceError(f"decision has already been debited: {decision_id}")
        if amount > self.remaining:
            raise ResourceError(
                f"action cost {amount} exceeds remaining daily budget {self.remaining}"
            )
        debit_id = sha256_value(
            {
                "action_id": action_id,
                "amount": amount,
                "budget_id": self.budget_id,
                "day": self.day,
                "decision_id": decision_id,
                "event_id": event_id,
            }
        )
        debit = ResourceDebit(
            debit_id=debit_id,
            event_id=event_id,
            decision_id=decision_id,
            action_id=action_id,
            amount=amount,
        )
        return DailyResourceLedger(
            day=self.day,
            budget_id=self.budget_id,
            total=self.total,
            remaining=self.remaining - amount,
            debits=(*self.debits, debit),
        )
