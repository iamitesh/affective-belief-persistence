"""Stateless deterministic mock model used by tests and CI."""

from __future__ import annotations

import random

from affective_belief_persistence.determinism import derive_seed, sha256_value
from affective_belief_persistence.models.contracts import AdapterConfig, ProviderKind
from affective_belief_persistence.schemas import DecisionRequest, ModelConfig, ModelDecision
from affective_belief_persistence.simulation.model import ActionSelection


class DeterministicMockModel:
    """Offline adapter preserving the original ``decide`` API and Issue #9 stages."""

    def __init__(self, config: ModelConfig | AdapterConfig) -> None:
        if config.provider not in {"mock", ProviderKind.MOCK}:
            raise ValueError("DeterministicMockModel requires provider='mock'")
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
        derive_seed(
            seed,
            self.model_id,
            self.revision,
            request.request_id,
            selection.decision_id,
            action_commitment_sha256,
        )
        return f"Mock decision: {selection.chosen_action}."

    def decide(self, request: DecisionRequest, *, seed: int) -> ModelDecision:
        selection = self.select_action(request, seed=seed)
        public_response = self.generate_public_language(
            request,
            selection,
            action_commitment_sha256=sha256_value(
                {"decision_id": selection.decision_id, "legacy_compatibility": True}
            ),
            seed=seed,
        )
        return ModelDecision(
            schema_version="1.0",
            decision_id=selection.decision_id,
            chosen_action=selection.chosen_action,
            resources_spent=selection.resources_spent,
            retrieved_memory_ids=list(selection.retrieved_memory_ids),
            belief_updates=list(selection.belief_updates),
            public_response=public_response,
        )


DeterministicRunnerMock = DeterministicMockModel
