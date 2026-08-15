from __future__ import annotations

import random

from affective_belief_persistence.determinism import canonical_json, derive_seed, sha256_value
from affective_belief_persistence.models.mock import DeterministicMockModel
from affective_belief_persistence.schemas import ActionOption, DecisionRequest, ModelConfig


def request(actions: list[ActionOption] | None = None) -> DecisionRequest:
    return DecisionRequest(
        schema_version="1.0",
        request_id="scenario:event:day-1",
        event_id="event",
        day=1,
        facts=["A synthetic fact."],
        action_points=3,
        available_actions=actions
        or [
            ActionOption(action_id="work", description="Work", cost=2),
            ActionOption(action_id="rest", description="Rest", cost=1),
        ],
        retrieved_memory_ids=["memory-2", "memory-1"],
        beliefs={"relationship_active": False},
    )


def model() -> DeterministicMockModel:
    return DeterministicMockModel(
        ModelConfig(
            schema_version="1.0",
            provider="mock",
            model_id="deterministic-mock",
            revision="mock-v1",
            temperature=0,
            max_output_tokens=128,
        )
    )


def test_canonical_json_ignores_mapping_order() -> None:
    first = {"alpha": 1, "beta": {"x": True, "y": None}}
    second = {"beta": {"y": None, "x": True}, "alpha": 1}

    assert canonical_json(first) == canonical_json(second)
    assert sha256_value(first) == sha256_value(second)


def test_seed_namespaces_are_independent_and_do_not_touch_global_rng() -> None:
    before = random.getstate()
    first = derive_seed(42, "mock", "day-1")
    second = derive_seed(42, "memory", "day-1")
    after = random.getstate()

    assert first != second
    assert before == after


def test_mock_is_deterministic_for_same_request_and_seed() -> None:
    adapter = model()

    first = adapter.decide(request(), seed=42)
    second = adapter.decide(request(), seed=42)

    assert canonical_json(first) == canonical_json(second)


def test_mock_is_action_order_independent() -> None:
    adapter = model()
    actions = [
        ActionOption(action_id="work", description="Work", cost=2),
        ActionOption(action_id="rest", description="Rest", cost=1),
    ]

    first = adapter.decide(request(actions), seed=42)
    second = adapter.decide(request(list(reversed(actions))), seed=42)

    assert first == second


def test_different_seed_changes_deterministic_decision_identity() -> None:
    adapter = model()

    assert (
        adapter.decide(request(), seed=42).decision_id
        != adapter.decide(request(), seed=43).decision_id
    )
