"""Safe collection of repository and environment provenance."""

from __future__ import annotations

import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from affective_belief_persistence.schemas import CodeState, EnvironmentState


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def collect_code_state(root: Path) -> CodeState:
    commit = _git(root, "rev-parse", "HEAD") or "unknown"
    status = _git(root, "status", "--porcelain", "--untracked-files=normal")
    return CodeState(commit=commit, dirty=bool(status) if status is not None else False)


def collect_environment() -> EnvironmentState:
    dependencies: dict[str, str] = {}
    for distribution in sorted(("pydantic", "PyYAML"), key=str.casefold):
        try:
            dependencies[distribution] = version(distribution)
        except PackageNotFoundError:
            dependencies[distribution] = "not-installed"
    return EnvironmentState(
        python=sys.version.split()[0],
        platform=platform.platform(),
        dependencies=dependencies,
    )
