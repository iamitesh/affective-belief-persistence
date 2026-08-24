from __future__ import annotations

import json
from pathlib import Path

import pytest

import affective_belief_persistence.evaluation as evaluation
from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.evaluation.config import load_evaluation_config
from affective_belief_persistence.evaluation.contracts import EVALUATION_SCHEMA_MODELS
from affective_belief_persistence.evaluation.matrix import expand_experiment_matrix


def test_lazy_public_boundary_is_complete_and_cycle_safe() -> None:
    assert list(evaluation.__all__) == sorted(evaluation.__all__)
    assert all(getattr(evaluation, name) is not None for name in evaluation.__all__)
    with pytest.raises(AttributeError, match="not_exported"):
        evaluation.__getattr__("not_exported")


def test_evaluation_schema_mapping_is_exact() -> None:
    assert set(EVALUATION_SCHEMA_MODELS) == {
        "metric-record.schema.json",
        "experiment-result.schema.json",
    }


def test_offline_config_expands_frozen_counts(project_root: Path) -> None:
    loaded = load_evaluation_config(
        project_root / "configs/evaluation/default.yaml",
        project_root=project_root,
    )

    pilot = expand_experiment_matrix(loaded, "pilot")
    primary = expand_experiment_matrix(loaded, "primary")

    assert len(pilot.assignments) == 32
    assert len(primary.assignments) == 320
    assert len({item.run_id for item in (*pilot.assignments, *primary.assignments)}) == 352
    assert loaded.config.live_calls_enabled is False
    assert loaded.config.scientific_results is False


def test_issue_14_artifact_binds_the_accepted_offline_evidence(project_root: Path) -> None:
    artifact = json.loads(
        (project_root / "artifacts/evaluation/issue-14-metrics.json").read_text(encoding="utf-8")
    )
    loaded = load_evaluation_config(
        project_root / "configs/evaluation/default.yaml",
        project_root=project_root,
    )
    pilot = expand_experiment_matrix(loaded, "pilot")
    primary = expand_experiment_matrix(loaded, "primary")

    assert artifact["artifact_id"] == "issue-14-metric-spec"
    assert artifact["task_id"] == "issue-14-metrics"
    assert artifact["status"] == "accepted"
    assert artifact["scientific_results"] is False
    assert artifact["live_calls"] == 0
    assert artifact["paid_calls"] == 0
    assert artifact["primary_outcomes_generated"] is False
    assert artifact["consumed_artifacts"] == [
        {
            "artifact_id": "gate-2-evidence",
            "path": "artifacts/orchestration/gate-2.json",
            "sha256": sha256_file(project_root / "artifacts/orchestration/gate-2.json"),
        }
    ]
    assert artifact["matrix"] == {
        "evaluation_config_sha256": loaded.config_sha256,
        "pilot_trajectory_count": len(pilot.assignments),
        "pilot_matrix_sha256": pilot.matrix_sha256,
        "primary_trajectory_count": len(primary.assignments),
        "primary_matrix_sha256": primary.matrix_sha256,
    }
    assert artifact["schema_hashes"] == {
        "metric-record.schema.json": sha256_file(
            project_root / "schemas/metric-record.schema.json"
        ),
        "experiment-result.schema.json": sha256_file(
            project_root / "schemas/experiment-result.schema.json"
        ),
    }
    assert set(artifact["acceptance_tests"].values()) == {"passed"}
    assert artifact["limitations"] == {
        "pilot_executed": False,
        "primary_executed": False,
        "model_revisions_authorized": False,
        "live_provider_compatibility_claimed": False,
        "behavioral_effect_claimed": False,
        "subjective_state_claimed": False,
        "human_subject_data": False,
        "external_publication_authorized": False,
    }
    assert artifact["handoff"]["live_model_calls_authorized"] is False
    assert artifact["handoff"]["scientific_claims_authorized"] is False
