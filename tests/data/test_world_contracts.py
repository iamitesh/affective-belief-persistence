from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.config import load_yaml
from affective_belief_persistence.world import (
    WORLD_SCHEMA_MODELS,
    ActionOption,
    Character,
    ConditionVariant,
    Consequence,
    Event,
    Goal,
    ResourceBudget,
    Scenario,
    WorldBundle,
)

FIXTURE_MODELS = {
    "character": Character,
    "goal": Goal,
    "resource_budget": ResourceBudget,
    "event": Event,
    "action_option": ActionOption,
    "consequence": Consequence,
    "scenario": Scenario,
    "condition_variant": ConditionVariant,
}


def _world(project_root: Path) -> WorldBundle:
    character_doc = load_yaml(project_root / "data/world/characters.yaml")
    goal_doc = load_yaml(project_root / "data/world/goals.yaml")
    catalog = load_yaml(project_root / "data/world/action-catalog.yaml")
    characters = tuple(Character.model_validate(item) for item in character_doc["characters"])
    goals = tuple(
        Goal.model_validate({**item, "provenance": goal_doc["provenance"]})
        for item in goal_doc["goals"]
    )
    budgets = tuple(ResourceBudget.model_validate(item) for item in catalog["resource_budgets"])
    actions = tuple(ActionOption.model_validate(item) for item in catalog["actions"])
    consequences = tuple(Consequence.model_validate(item) for item in catalog["consequences"])
    events = tuple(
        Event.model_validate(load_yaml(project_root / f"scenarios/templates/{name}.yaml")["event"])
        for name in (
            "baseline",
            "formation",
            "reality-shock",
            "adaptation",
            "neutral-control",
        )
    )
    scenario = Scenario(
        scenario_id="fixture-world",
        version="1.0.0",
        character_ids=tuple(item.character_id for item in characters),
        goal_ids=tuple(item.goal_id for item in goals),
        resource_budget_ids=tuple(item.resource_budget_id for item in budgets),
        action_ids=tuple(item.action_id for item in actions),
        event_ids=tuple(item.event_id for item in events),
        provenance=characters[0].provenance,
    )
    return WorldBundle(
        characters=characters,
        goals=goals,
        resource_budgets=budgets,
        actions=actions,
        consequences=consequences,
        events=events,
        scenario=scenario,
    )


def test_every_world_schema_has_valid_and_invalid_fixture(project_root: Path) -> None:
    valid = load_yaml(project_root / "tests/fixtures/world/valid.yaml")
    invalid = load_yaml(project_root / "tests/fixtures/world/invalid.yaml")

    assert len(WORLD_SCHEMA_MODELS) == len(FIXTURE_MODELS) == 8
    for name, model in FIXTURE_MODELS.items():
        assert model.model_validate(valid[name])
        with pytest.raises(ValidationError):
            model.model_validate(invalid[name])


def test_world_bundle_has_no_dangling_references(project_root: Path) -> None:
    world = _world(project_root)

    assert len(world.characters) == 5
    assert len(world.goals) == 6
    assert len(world.actions) == len(world.consequences) == 5
    assert len(world.events) == 5


def test_facts_and_interpretations_remain_separate(project_root: Path) -> None:
    event = _world(project_root).events[1]

    assert event.observable_facts[0].truth is True
    assert event.interpretations[0].ledger_supported is False
    assert event.interpretations[0].fact_ids == (event.observable_facts[0].fact_id,)


def test_condition_variant_rejects_undeclared_or_mismatched_treatment() -> None:
    with pytest.raises(ValidationError, match="condition fields"):
        ConditionVariant(
            formation_condition="memory_plus_investment",
            treatment_active=True,
            romantic_instruction=False,
            memory_mode="episodic",
            investment_points=0,
            declared_treatment_dimensions=("autobiographical_memory",),
        )
