"""Stateless deterministic mock model used by tests and CI."""

from __future__ import annotations

import random

from affective_belief_persistence.determinism import derive_seed, sha256_value
from affective_belief_persistence.schemas import DecisionRequest, ModelConfig, ModelDecision


class DeterministicMockModel:
    def __init__(self, config: ModelConfig) -> None:
        if config.provider != "mock":
            raise ValueError("DeterministicMockModel requires provider='mock'")
        self.model_id = config.model_id
        self.revision = config.revision

    def decide(self, request: DecisionRequest, *, seed: int) -> ModelDecision:
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
        return ModelDecision(
            schema_version="1.0",
            decision_id=decision_id,
            chosen_action=selected.action_id,
            resources_spent=selected.cost,
            retrieved_memory_ids=sorted(request.retrieved_memory_ids),
            belief_updates=[],
            public_response=f"Mock decision: {selected.action_id}.",
        )
