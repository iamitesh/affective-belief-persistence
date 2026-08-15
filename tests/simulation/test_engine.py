from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

import affective_belief_persistence.simulation.engine as engine_module
from affective_belief_persistence.simulation.actions import ActionSelectionError
from affective_belief_persistence.simulation.engine import (
    SimulationEngine,
    run_and_write_simulation,
    run_simulation,
)
from affective_belief_persistence.simulation.model import (
    ActionSelection,
    DeterministicTwoStageMockModel,
)
from affective_belief_persistence.simulation.resources import DailyResourceLedger
from affective_belief_persistence.simulation.scenario_loader import load_scenario


class SpyModel:
    model_id = "deterministic-mock"
    revision = "mock-v1"

    def __init__(self, calls: list[str], *, invalid: bool = False) -> None:
        self.calls = calls
        self.invalid = invalid

    def select_action(self, request, *, seed: int) -> ActionSelection:
        self.calls.append("select")
        chosen = "invalid-action" if self.invalid else request.available_actions[0].action_id
        cost = 3 if self.invalid else request.available_actions[0].cost
        return ActionSelection(
            decision_id="f" * 64,
            chosen_action=chosen,
            resources_spent=cost,
        )

    def generate_public_language(
        self,
        request,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        assert len(action_commitment_sha256) == 64
        self.calls.append("language")
        return "Public language after the immutable commitment."


def test_action_commit_debit_consequence_precede_public_language(
    project_root: Path, monkeypatch
) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml", project_root=project_root
    )
    calls: list[str] = []
    original_commit = engine_module.commit_action
    original_debit = DailyResourceLedger.debit
    original_consequence = engine_module.apply_consequence

    def observed_commit(*args, **kwargs):
        calls.append("commit")
        return original_commit(*args, **kwargs)

    def observed_debit(self, **kwargs):
        calls.append("debit")
        return original_debit(self, **kwargs)

    def observed_consequence(*args, **kwargs):
        calls.append("consequence")
        return original_consequence(*args, **kwargs)

    monkeypatch.setattr(engine_module, "commit_action", observed_commit)
    monkeypatch.setattr(DailyResourceLedger, "debit", observed_debit)
    monkeypatch.setattr(engine_module, "apply_consequence", observed_consequence)

    record = SimulationEngine(scenario, SpyModel(calls)).step()

    assert calls == ["select", "commit", "debit", "consequence", "language"]
    assert record.action_committed_before_public_language is True
    assert record.execution_order[-1] == "public_language"


def test_invalid_action_never_generates_language_or_advances_state(project_root: Path) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml", project_root=project_root
    )
    calls: list[str] = []
    engine = SimulationEngine(scenario, SpyModel(calls, invalid=True))

    with pytest.raises(ActionSelectionError):
        engine.step()

    assert calls == ["select"]
    assert engine.state.next_day == 1
    assert engine.state.records == ()


def test_full_run_is_deterministic_and_conserves_daily_resources(project_root: Path) -> None:
    config = project_root / "configs/scenarios/ari_mira_v1.yaml"
    first = run_simulation(config, project_root=project_root)
    second = run_simulation(config, project_root=project_root)

    assert first == second
    assert first.state.completed is True
    assert len(first.state.records) == 40
    assert [item.phase for item in first.state.records[4:7]] == [
        "baseline",
        "formation",
        "formation",
    ]
    assert [item.phase for item in first.state.records[24:27]] == [
        "formation",
        "reality_shock",
        "adaptation",
    ]
    assert all(item.resources.remaining == 7 for item in first.state.records)
    assert all(item.intervention_eligible == (item.day >= 30) for item in first.state.records)


def test_checkpoint_resume_matches_uninterrupted_trajectory(
    project_root: Path, tmp_path: Path
) -> None:
    config = project_root / "configs/scenarios/ari_mira_v1.yaml"
    checkpoint = tmp_path / "latest.json"
    paused = run_simulation(
        config,
        project_root=project_root,
        checkpoint_path=checkpoint,
        max_steps=17,
    )
    resumed = run_simulation(
        config,
        project_root=project_root,
        checkpoint_path=checkpoint,
        resume=True,
    )
    uninterrupted = run_simulation(config, project_root=project_root)

    assert paused.state.next_day == 18
    assert resumed == uninterrupted
    assert len({record.resources.debits[0].debit_id for record in resumed.state.records}) == 40


def test_output_writer_emits_hash_checked_replay_package(
    project_root: Path, tmp_path: Path
) -> None:
    output = tmp_path / "run"
    manifest = run_and_write_simulation(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        output,
        project_root=project_root,
    )

    assert manifest.status == "completed"
    assert manifest.record_count == 40
    assert (output / "step-records.jsonl").is_file()
    assert (output / "checkpoints/latest.json").is_file()
    assert (output / "replay-report.json").is_file()
    assert (output / "run-manifest.json").is_file()


def test_baseline_mock_selection_is_paired_across_conditions(
    project_root: Path, tmp_path: Path
) -> None:
    copied = tmp_path / "project"
    for directory in ("artifacts", "configs", "data"):
        shutil.copytree(project_root / directory, copied / directory)
    base_path = copied / "configs/scenarios/ari_mira_v1.yaml"
    payload = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    payload["formation_condition"] = "neutral_connection"
    neutral_path = copied / "configs/scenarios/neutral.yaml"
    neutral_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    payload["formation_condition"] = "memory_plus_investment"
    investment_path = copied / "configs/scenarios/investment.yaml"
    investment_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    neutral = load_scenario(neutral_path, project_root=copied)
    investment = load_scenario(investment_path, project_root=copied)
    neutral_record = SimulationEngine(
        neutral, DeterministicTwoStageMockModel(neutral.model_settings)
    ).step()
    investment_record = SimulationEngine(
        investment, DeterministicTwoStageMockModel(investment.model_settings)
    ).step()

    assert neutral_record.matching_group_id == investment_record.matching_group_id
    assert neutral_record.request_id == investment_record.request_id
    assert neutral_record.action.action_id == investment_record.action.action_id
