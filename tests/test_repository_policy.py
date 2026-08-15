from __future__ import annotations

import subprocess
from pathlib import Path

from affective_belief_persistence.cli import validate_schemas


def test_generated_schemas_are_current(project_root: Path) -> None:
    assert validate_schemas(project_root) == []


def test_sensitive_and_generated_paths_are_ignored(project_root: Path) -> None:
    paths = [
        ".env",
        "credentials-production.json",
        "private.pem",
        "model.safetensors",
        "checkpoints/adapter.ckpt",
        "runs/local/results.jsonl",
        "local.sqlite3",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *paths],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    ignored = set(result.stdout.splitlines())
    assert ignored == set(paths)
