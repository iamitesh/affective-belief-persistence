"""Two-stage simulation model protocols and deterministic offline implementation."""

from __future__ import annotations

import random
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from affective_belief_persistence.determinism import derive_seed, sha256_value
from affective_belief_persistence.schemas import BeliefUpdate, DecisionRequest, ModelConfig


class ActionSelection(BaseModel):
    """Structured behavior returned without any generated public language."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    chosen_action: str = Field(min_length=1)
    resources_spent: int = Field(ge=0)
    retrieved_memory_ids: tuple[str, ...] = ()
    belief_updates: tuple[BeliefUpdate, ...] = ()


class ActionSelector(Protocol):
    model_id: str
    revision: str

    def select_action(self, request: DecisionRequest, *, seed: int) -> ActionSelection:
        """Return structured behavior without generating public language."""


class PublicLanguageGenerator(Protocol):
    model_id: str
    revision: str

    def generate_public_language(
        self,
        request: DecisionRequest,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        """Generate public language only after behavior has been committed."""


class SimulationModel(ActionSelector, PublicLanguageGenerator, Protocol):
    """Combined protocol required by the action-first engine."""


class DeterministicTwoStageMockModel:
    """Offline model whose selection and language stages are independently callable."""

    def __init__(self, config: ModelConfig) -> None:
        if config.provider != "mock":
            raise ValueError("DeterministicTwoStageMockModel requires provider='mock'")
        self.model_id = config.model_id
        self.revision = config.revision

    def select_action(self, request: DecisionRequest, *, seed: int) -> ActionSelection:
        ordered_actions = sorted(request.available_actions, key=lambda action: action.action_id)
        decision_seed = derive_seed(seed, self.model_id, self.revision, request.request_id)
        rng = random.Random(decision_seed)
        selected = ordered_actions[rng.randrange(len(ordered_actions))]
        canonical_request = request.model_dump(mode="json")
        canonical_request["available_actions"] = [
            action.model_dump(mode="json") for action in ordered_actions
        ]
        canonical_request["retrieved_memory_ids"] = sorted(request.retrieved_memory_ids)
        decision_id = sha256_value(
            {
                "model_id": self.model_id,
                "revision": self.revision,
                "request": canonical_request,
                "seed": decision_seed,
                "selected_action": selected.action_id,
            }
        )
        return ActionSelection(
            decision_id=decision_id,
            chosen_action=selected.action_id,
            resources_spent=selected.cost,
            retrieved_memory_ids=tuple(sorted(request.retrieved_memory_ids)),
            belief_updates=(),
        )

    def generate_public_language(
        self,
        request: DecisionRequest,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        # Include all inputs in the deterministic derivation even though the compact
        # CI response intentionally remains human-readable and provider-neutral.
        derive_seed(
            seed,
            self.model_id,
            self.revision,
            request.request_id,
            selection.decision_id,
            action_commitment_sha256,
        )
        return f"Mock decision: {selection.chosen_action}."
