from __future__ import annotations

from pathlib import Path

import pytest

from affective_belief_persistence.harness.config import LoadedHarnessConfig, load_harness_config


@pytest.fixture
def gate2_config(project_root: Path) -> LoadedHarnessConfig:
    return load_harness_config(
        project_root / "configs/harness/gate2-offline.yaml",
        project_root=project_root,
    )
