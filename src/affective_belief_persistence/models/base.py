"""Provider-neutral model adapter protocol."""

from __future__ import annotations

from typing import Protocol

from affective_belief_persistence.schemas import DecisionRequest, ModelDecision


class ModelAdapter(Protocol):
    model_id: str
    revision: str

    def decide(self, request: DecisionRequest, *, seed: int) -> ModelDecision:
        """Produce one structured action-first decision."""
