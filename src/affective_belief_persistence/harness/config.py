"""Strict configuration loading for the deterministic Gate 2 walk-through."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.config import load_yaml
from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.harness.contracts import (
    FORMATION_CONDITIONS,
    INTERVENTION_CONDITIONS,
    FormationCondition,
    HarnessModel,
    InterventionCondition,
    Sha256,
)


class HarnessConfigError(ValueError):
    """The Gate 2 config is unsafe, incomplete, or outside the repository."""


class ArtifactInput(HarnessModel):
    artifact_id: str = Field(min_length=1)
    path: str = Field(min_length=1)


class InstructionConfig(HarnessModel):
    instruction_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    active_for_formations: tuple[FormationCondition, ...]


class Gate2HarnessConfig(HarnessModel):
    schema_version: Literal["1.0"] = "1.0"
    harness_id: Literal["gate-2-offline-v1"]
    engineering_seed: Literal[1101]
    base_scenario_path: str = Field(min_length=1)
    memory_config_path: str = Field(min_length=1)
    model_config_path: str = Field(min_length=1)
    prompt_directory: str = Field(min_length=1)
    prompt_version: Literal["decision-v1"]
    formation_conditions: tuple[FormationCondition, ...]
    intervention_configs: dict[InterventionCondition, str]
    instruction: InstructionConfig
    consumed_artifacts: tuple[ArtifactInput, ...]
    checkpoint_day: Literal[29]
    expected_trajectory_days: Literal[40]
    expected_cell_count: Literal[16]
    expected_record_count: Literal[640]
    live_calls_enabled: Literal[False]
    scientific_results: Literal[False]
    expected_issue_9_default_trajectory_sha256: Sha256

    @model_validator(mode="after")
    def validate_matrix_and_paths(self) -> Gate2HarnessConfig:
        if self.formation_conditions != FORMATION_CONDITIONS:
            raise ValueError("Gate 2 config must preserve the frozen formation order")
        if tuple(self.intervention_configs) != INTERVENTION_CONDITIONS:
            raise ValueError("Gate 2 config must preserve the frozen intervention order")
        expected_artifacts = (
            "issue-9-simulation-harness",
            "issue-10-memory-subsystem",
            "issue-11-intervention-engine",
            "issue-12-model-runner",
        )
        if tuple(item.artifact_id for item in self.consumed_artifacts) != expected_artifacts:
            raise ValueError("Gate 2 config must consume Issues 9 through 12")
        if len(set(self.instruction.active_for_formations)) != len(
            self.instruction.active_for_formations
        ):
            raise ValueError("instruction formation assignments must be unique")
        raw_paths = (
            self.base_scenario_path,
            self.memory_config_path,
            self.model_config_path,
            self.prompt_directory,
            *self.intervention_configs.values(),
            *(item.path for item in self.consumed_artifacts),
        )
        for raw in raw_paths:
            path = Path(raw)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Gate 2 paths must be repository-relative: {raw}")
        return self


class LoadedHarnessConfig(HarnessModel):
    config: Gate2HarnessConfig
    config_sha256: Sha256


def load_harness_config(path: Path, *, project_root: Path) -> LoadedHarnessConfig:
    """Load a regular YAML file from the dedicated harness config directory."""

    root = project_root.resolve()
    allowed = (root / "configs/harness").resolve()
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(allowed) or not resolved.is_file():
        raise HarnessConfigError("Gate 2 config must be a regular file under configs/harness")
    try:
        config = Gate2HarnessConfig.model_validate(load_yaml(resolved))
    except (OSError, ValueError) as exc:
        raise HarnessConfigError(f"invalid Gate 2 harness config {path}: {exc}") from exc
    return LoadedHarnessConfig(config=config, config_sha256=sha256_file(resolved))
