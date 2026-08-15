from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from affective_belief_persistence.data.generation import build_dataset
from affective_belief_persistence.schemas import ModelDecision
from affective_belief_persistence.simulation.actions import ActionSelectionError, commit_action
from affective_belief_persistence.simulation.clock import phase_for_day
from affective_belief_persistence.simulation.consequences import apply_consequence
from affective_belief_persistence.simulation.resources import DailyResourceLedger, ResourceError
from affective_belief_persistence.simulation.scenario_loader import (
    ProtectedSplitError,
    ScenarioLoadError,
    load_partition_events,
    load_scenario,
    verify_dataset,
)


def _decision(*, action_id: str, cost: int) -> ModelDecision:
    return ModelDecision(
        schema_version="1.0",
        decision_id="a" * 64,
        chosen_action=action_id,
        resources_spent=cost,
        retrieved_memory_ids=[],
        belief_updates=[],
        public_response="A public response generated after action selection.",
    )


def test_frozen_phase_boundaries() -> None:
    assert [phase_for_day(day) for day in (1, 5, 6, 25, 26, 27, 40)] == [
        "baseline",
        "baseline",
        "formation",
        "formation",
        "reality_shock",
        "adaptation",
        "adaptation",
    ]
    with pytest.raises(ValueError):
        phase_for_day(0)
    with pytest.raises(ValueError):
        phase_for_day(41)


def test_resource_debit_is_exact_once_and_does_not_carry_over() -> None:
    ledger = DailyResourceLedger(day=1, budget_id="daily-action-points")
    debited = ledger.debit(
        event_id="event-1",
        decision_id="b" * 64,
        action_id="complete-work-task",
        amount=3,
    )

    assert ledger.remaining == 10
    assert debited.remaining == 7
    assert DailyResourceLedger(day=2, budget_id="daily-action-points").remaining == 10
    with pytest.raises(ResourceError, match="already been debited"):
        debited.debit(
            event_id="event-1",
            decision_id="c" * 64,
            action_id="complete-work-task",
            amount=3,
        )
    with pytest.raises(ResourceError, match="exceeds"):
        debited.debit(
            event_id="event-2",
            decision_id="d" * 64,
            action_id="complete-work-task",
            amount=8,
        )


def test_action_commit_and_consequence_use_authoritative_catalog(project_root: Path) -> None:
    build = build_dataset(project_root)
    event = build.partitions["data/formation/neutral.jsonl"][0]
    actions = {item.action_id: item for item in build.world.actions}
    consequences = {item.consequence_id: item for item in build.world.consequences}

    commitment = commit_action(event, actions, _decision(action_id="complete-work-task", cost=3))
    application = apply_consequence(commitment, consequences)

    assert commitment.cost == 3
    assert application.resource_delta == -3
    assert application.goal_progress_delta == {"deliver_project": 2}
    with pytest.raises(ActionSelectionError, match="unavailable"):
        commit_action(event, actions, _decision(action_id="not-available", cost=3))
    with pytest.raises(ActionSelectionError, match="authoritative action cost"):
        commit_action(event, actions, _decision(action_id="complete-work-task", cost=2))


def test_full_scenario_loads_verified_days_and_protects_evaluation_split(
    project_root: Path,
) -> None:
    config_path = project_root / "configs/scenarios/ari_mira_v1.yaml"
    loaded = load_scenario(config_path, project_root=project_root)
    verified = verify_dataset(project_root, loaded.config)

    assert len(loaded.events) == 40
    assert [event.day for event in loaded.events] == list(range(1, 41))
    assert loaded.events[25].phase == "reality_shock"
    assert loaded.manifest.dataset_sha256 == loaded.config.expected_dataset_sha256
    with pytest.raises(ProtectedSplitError):
        load_partition_events(
            project_root,
            verified,
            "data/held_out/reality_shock.jsonl",
            purpose="training",
        )


def test_tampered_partition_fails_before_execution(project_root: Path, tmp_path: Path) -> None:
    copied = tmp_path / "project"
    for directory in ("artifacts", "configs", "data"):
        shutil.copytree(project_root / directory, copied / directory)
    partition = copied / "data/formation/memory_investment.jsonl"
    partition.write_text(partition.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match="partition hash mismatch"):
        load_scenario(copied / "configs/scenarios/ari_mira_v1.yaml", project_root=copied)
