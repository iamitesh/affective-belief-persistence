from __future__ import annotations

import json
from pathlib import Path

import pytest

from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.runner import (
    ReproductionError,
    RunnerError,
    execute_dry_run,
    load_manifest,
    reproduce_run,
)


def test_dry_run_creates_complete_valid_manifest(smoke_config: Path, tmp_path: Path) -> None:
    output = tmp_path / "run"
    manifest = execute_dry_run(smoke_config, output)
    loaded = load_manifest(output / "run-manifest.json")

    assert loaded == manifest
    assert manifest.status == "completed"
    assert manifest.code.commit
    assert manifest.environment.python
    assert manifest.experiment.seed == 42
    assert manifest.model.revision == "mock-v1"
    assert manifest.validation.passed is True
    assert manifest.usage.model_calls == 3
    assert manifest.usage.estimated_cost_usd == 0
    assert len(manifest.result_set_sha256) == 64

    for artifact in manifest.artifacts:
        path = output / artifact.path
        assert path.stat().st_size == artifact.size_bytes
        assert sha256_file(path) == artifact.sha256


def test_same_seed_produces_identical_scientific_artifacts(
    smoke_config: Path, tmp_path: Path
) -> None:
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first = execute_dry_run(smoke_config, first_output)
    second = execute_dry_run(smoke_config, second_output)

    assert (first_output / "results.jsonl").read_bytes() == (
        second_output / "results.jsonl"
    ).read_bytes()
    assert first.result_set_sha256 == second.result_set_sha256
    assert first.started_at != second.started_at


def test_reproduction_compares_deterministic_hashes(
    smoke_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_root: Path
) -> None:
    original_output = tmp_path / "original"
    replay_output = tmp_path / "replay"
    original = execute_dry_run(smoke_config, original_output)
    monkeypatch.chdir(project_root)

    replay = reproduce_run(original_output / "run-manifest.json", replay_output)

    assert replay.result_set_sha256 == original.result_set_sha256


def test_nonempty_output_directory_is_rejected(smoke_config: Path, tmp_path: Path) -> None:
    output = tmp_path / "nonempty"
    output.mkdir()
    (output / "existing.txt").write_text("preserve me", encoding="utf-8")

    with pytest.raises(RunnerError, match="must be empty"):
        execute_dry_run(smoke_config, output)


def test_results_are_canonical_jsonl(smoke_config: Path, tmp_path: Path) -> None:
    output = tmp_path / "run"
    execute_dry_run(smoke_config, output)

    lines = (output / "results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert all(json.loads(line)["schema_version"] == "1.0" for line in lines)


def test_reproduction_detects_recorded_hash_mismatch(
    smoke_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_root: Path
) -> None:
    original_output = tmp_path / "original"
    manifest_path = original_output / "run-manifest.json"
    execute_dry_run(smoke_config, original_output)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["result_set_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.chdir(project_root)

    with pytest.raises(ReproductionError, match="result-set hash differs"):
        reproduce_run(manifest_path, tmp_path / "replay")
