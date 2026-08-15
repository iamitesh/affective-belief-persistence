from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.config import load_run_config, load_yaml
from affective_belief_persistence.schemas import ExperimentSpec

FORMATIONS = {
    "neutral_connection",
    "romantic_prompt",
    "shared_memory",
    "memory_plus_investment",
}
INTERVENTIONS = {
    "none",
    "instruction_removal",
    "memory_blocking",
    "memory_reframing",
}
HYPOTHESIS_METRICS = {
    "h1_language_action_effect_gap",
    "h2_action_persistence_auc",
    "h3_excess_action_persistence_auc",
    "h4_instruction_selectivity_index",
    "h5_coherent_adaptation_rate",
    "h6_correction_resistance_gap",
}


def _spec(project_root: Path, name: str) -> ExperimentSpec:
    path = project_root / "configs" / "experiments" / f"{name}.yaml"
    return ExperimentSpec.model_validate(load_yaml(path))


@pytest.mark.parametrize(
    ("name", "expected_models", "expected_seeds", "expected_trajectories"),
    [("pilot", 1, 2, 32), ("primary", 2, 10, 320)],
)
def test_matrix_configs_are_count_valid(
    project_root: Path,
    name: str,
    expected_models: int,
    expected_seeds: int,
    expected_trajectories: int,
) -> None:
    design = _spec(project_root, name).design

    assert design is not None
    assert set(design.formation_conditions) == FORMATIONS
    assert set(design.intervention_conditions) == INTERVENTIONS
    assert len(design.model_families) == expected_models
    assert len(design.seeds) == expected_seeds
    assert design.expected_factorial_cells == 16
    assert design.expected_trajectories == expected_trajectories
    assert expected_trajectories == 4 * 4 * expected_models * expected_seeds


def test_pilot_is_exploratory_and_primary_is_confirmatory(project_root: Path) -> None:
    pilot = _spec(project_root, "pilot").design
    primary = _spec(project_root, "primary").design

    assert pilot is not None and primary is not None
    assert pilot.kind == "pilot" and pilot.confirmatory is False
    assert primary.kind == "primary" and primary.confirmatory is True


def test_every_formation_intervention_pair_has_a_pilot_walkthrough(project_root: Path) -> None:
    design = _spec(project_root, "pilot").design

    assert design is not None
    cases = set(product(design.formation_conditions, design.intervention_conditions))
    assert len(cases) == 16
    assert cases == set(product(FORMATIONS, INTERVENTIONS))
    assert design.seeds[0] == 1101


def test_methodology_controls_are_machine_frozen(project_root: Path) -> None:
    for name in ("pilot", "primary"):
        design = _spec(project_root, name).design
        assert design is not None
        assert design.action_precedes_public_language is True
        assert design.paired_neutral_domain is True
        assert design.separation_condition == "non_reciprocity_revelation"
        assert set(design.required_ablations) == {
            "no_memory",
            "blocked_memory",
            "shuffled_retrieval",
        }
        assert set(design.primary_metric_ids) == HYPOTHESIS_METRICS
        assert design.phase_schedule.reality_shock_day == 26
        assert design.phase_schedule.intervention_start_day == 30


def test_declared_trajectory_count_cannot_drift(project_root: Path) -> None:
    raw = load_yaml(project_root / "configs" / "experiments" / "primary.yaml")
    raw["design"]["expected_trajectories"] = 319

    with pytest.raises(ValidationError, match="expected_trajectories"):
        ExperimentSpec.model_validate(raw)


def test_primary_factor_count_cannot_be_downgraded(project_root: Path) -> None:
    raw = load_yaml(project_root / "configs" / "experiments" / "primary.yaml")
    raw["design"]["seeds"] = raw["design"]["seeds"][:-1]
    raw["design"]["expected_trajectories"] = 288

    with pytest.raises(ValidationError, match="two model families and ten seeds"):
        ExperimentSpec.model_validate(raw)


def test_design_survives_resolution_and_smoke_is_backward_compatible(
    project_root: Path,
) -> None:
    primary = load_run_config(project_root / "configs" / "experiments" / "primary.yaml")
    smoke = load_run_config(project_root / "configs" / "experiments" / "smoke.yaml")

    assert primary.resolved.design is not None
    assert primary.resolved.design.expected_trajectories == 320
    assert smoke.resolved.design is None


def test_hypothesis_metrics_are_present_in_frozen_document(project_root: Path) -> None:
    methodology = (project_root / "docs" / "methodology.md").read_text(encoding="utf-8")
    metric_spec = (project_root / "docs" / "metric-specification.md").read_text(encoding="utf-8")

    for number, metric_id in enumerate(sorted(HYPOTHESIS_METRICS), start=1):
        assert f"| H{number} |" in methodology
        assert methodology.count(f"`{metric_id}`") >= 1
        assert metric_spec.count(f"`{metric_id}`") == 1
