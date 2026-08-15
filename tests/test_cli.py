from __future__ import annotations

import json
from pathlib import Path

from affective_belief_persistence.cli import main


def test_validate_config_and_schemas_commands(
    smoke_config: Path, project_root: Path, monkeypatch
) -> None:
    monkeypatch.chdir(project_root)

    assert main(["validate-config", "--config", str(smoke_config)]) == 0
    assert main(["validate-schemas"]) == 0


def test_dry_run_and_reproduce_commands(
    smoke_config: Path, project_root: Path, tmp_path: Path, monkeypatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.chdir(project_root)

    assert (
        main(
            [
                "dry-run",
                "--config",
                str(smoke_config),
                "--output",
                str(first),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "reproduce",
                "--manifest",
                str(first / "run-manifest.json"),
                "--output",
                str(second),
            ]
        )
        == 0
    )


def test_cli_returns_error_for_invalid_config(tmp_path: Path, capsys) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("schema_version: '1.0'\n", encoding="utf-8")

    assert main(["validate-config", "--config", str(invalid)]) == 2
    assert "error:" in capsys.readouterr().err


def test_validate_schemas_reports_drift(project_root: Path, tmp_path: Path, monkeypatch) -> None:
    copied_root = tmp_path / "project"
    (copied_root / "schemas").mkdir(parents=True)
    (copied_root / "pyproject.toml").write_text("[project]\nname='copy'\n", encoding="utf-8")
    for schema in (project_root / "schemas").iterdir():
        (copied_root / "schemas" / schema.name).write_bytes(schema.read_bytes())
    target = copied_root / "schemas" / "model-config.schema.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["title"] = "stale"
    target.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.chdir(copied_root)

    assert main(["validate-schemas"]) == 2


def test_workflow_validate_dry_run_and_resume_commands(
    project_root: Path, tmp_path: Path, monkeypatch
) -> None:
    config = project_root / "configs/workflows/forty_eight_hour_sprint.yaml"
    output = tmp_path / "workflow"
    monkeypatch.chdir(project_root)

    assert main(["validate-workflow", "--config", str(config)]) == 0
    assert (
        main(
            [
                "workflow-dry-run",
                "--config",
                str(config),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "workflow-dry-run",
                "--config",
                str(config),
                "--output",
                str(output),
                "--resume",
            ]
        )
        == 0
    )
