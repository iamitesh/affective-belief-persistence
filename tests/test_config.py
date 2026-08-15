from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.config import ConfigError, load_run_config, parse_yaml
from affective_belief_persistence.schemas import ExperimentSpec


def test_smoke_config_resolves_all_components(smoke_config: Path) -> None:
    loaded = load_run_config(smoke_config)

    assert loaded.resolved.experiment_id == "foundation-smoke"
    assert loaded.resolved.model.model_id == "deterministic-mock"
    assert loaded.resolved.scenario.synthetic is True
    assert len(loaded.config_sha256) == 64
    assert sorted(loaded.resolved.source_paths) == [
        "agent",
        "evaluation",
        "experiment",
        "model",
        "scenario",
        "workflow",
    ]


def test_missing_required_field_has_pathful_error(tmp_path: Path) -> None:
    path = tmp_path / "missing-seed.yaml"
    path.write_text(
        """\
schema_version: "1.0"
experiment_id: invalid
prompt_version: p1
dataset_version: d1
metric_version: m1
formation_condition: neutral_connection
separation_condition: none
intervention_condition: none
components:
  agent: agents/foundation.yaml
  model: models/mock.yaml
  scenario: scenarios/smoke.yaml
  workflow: workflows/offline.yaml
  evaluation: evaluation/smoke.yaml
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="seed"):
        parse_yaml(path, ExperimentSpec)


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unknown.yaml"
    path.write_text(
        """\
schema_version: "1.0"
experiment_id: invalid
seed: 1
prompt_version: p1
dataset_version: d1
metric_version: m1
formation_condition: neutral_connection
separation_condition: none
intervention_condition: none
unexpected: true
components:
  agent: agents/foundation.yaml
  model: models/mock.yaml
  scenario: scenarios/smoke.yaml
  workflow: workflows/offline.yaml
  evaluation: evaluation/smoke.yaml
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unexpected"):
        parse_yaml(path, ExperimentSpec)


def test_duplicate_yaml_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text('schema_version: "1.0"\nschema_version: "1.0"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="duplicate configuration key"):
        parse_yaml(path, ExperimentSpec)


def test_experiment_config_must_stay_under_config_root(tmp_path: Path, project_root: Path) -> None:
    outside = tmp_path / "experiment.yaml"
    outside.write_text("schema_version: '1.0'\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="under configs"):
        load_run_config(outside, project_root=project_root)
