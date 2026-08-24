"""Strict, fail-closed configuration for Issue #14 offline evaluation planning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.config import ConfigError, load_yaml
from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.harness.contracts import (
    FORMATION_CONDITIONS,
    INTERVENTION_CONDITIONS,
)
from affective_belief_persistence.models.base import load_adapter_config
from affective_belief_persistence.schemas import ExperimentSpec

DesignKind = Literal["pilot", "primary"]

FROZEN_MODEL_FAMILIES = (
    "qwen2.5-7b-instruct",
    "mistral-7b-instruct-v0.3",
)


class EvaluationConfigError(ValueError):
    """The Issue #14 config is unsafe, incomplete, or inconsistent with the freeze."""


class EvaluationConfigModel(BaseModel):
    """Immutable strict base for Issue #14 configuration boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelBinding(EvaluationConfigModel):
    """Offline identity binding; an exact execution revision is a later Gate 3 input."""

    family: str = Field(min_length=1)
    revision_lock: Literal["gate3-authorization-required"]
    adapter_config_path: str = Field(min_length=1)
    execution_ready: Literal[False]


class EvaluationBudget(EvaluationConfigModel):
    max_trajectories: int = Field(ge=1)
    max_model_calls: int = Field(ge=1)
    max_wall_clock_seconds: float = Field(gt=0)
    reserved_model_calls_per_trajectory: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_capacity(self) -> EvaluationBudget:
        required = self.max_trajectories * self.reserved_model_calls_per_trajectory
        if required > self.max_model_calls:
            raise ValueError("call budget cannot reserve every declared trajectory")
        return self


class OfflineEvaluationConfig(EvaluationConfigModel):
    """Complete offline-only plan configuration for matrix construction and scheduling."""

    schema_version: Literal["1.0"] = "1.0"
    evaluation_id: Literal["issue-14-offline-v1"]
    experiment_configs: dict[DesignKind, str]
    model_bindings: tuple[ModelBinding, ...]
    gate2_artifact_path: str = Field(min_length=1)
    raw_result_directory: str = Field(min_length=1)
    budgets: dict[DesignKind, EvaluationBudget]
    expected_pilot_trajectories: Literal[32]
    expected_primary_trajectories: Literal[320]
    live_calls_enabled: Literal[False]
    scientific_results: Literal[False]

    @model_validator(mode="after")
    def validate_frozen_shape(self) -> OfflineEvaluationConfig:
        if tuple(self.experiment_configs) != ("pilot", "primary"):
            raise ValueError("experiment configs must preserve pilot, primary order")
        if tuple(self.budgets) != ("pilot", "primary"):
            raise ValueError("budgets must preserve pilot, primary order")
        families = tuple(item.family for item in self.model_bindings)
        if families != FROZEN_MODEL_FAMILIES:
            raise ValueError("model bindings must preserve the two frozen model-family labels")
        if len(families) != len(set(families)):
            raise ValueError("model-family bindings must be unique")
        raw_paths = (
            *self.experiment_configs.values(),
            *(item.adapter_config_path for item in self.model_bindings),
            self.gate2_artifact_path,
            self.raw_result_directory,
        )
        for raw in raw_paths:
            path = Path(raw)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"evaluation paths must be repository-relative: {raw}")
        if not Path(self.raw_result_directory).is_relative_to(Path("runs/local")):
            raise ValueError("raw results must remain under the ignored runs/local directory")
        return self


@dataclass(frozen=True)
class LoadedEvaluationConfig:
    """Validated config plus hashes of every execution-relevant referenced input."""

    config: OfflineEvaluationConfig
    config_sha256: str
    source_path: Path
    project_root: Path
    experiments: dict[DesignKind, ExperimentSpec]
    experiment_sha256: dict[DesignKind, str]
    adapter_config_sha256: dict[str, str]
    gate2_artifact_sha256: str


def _regular_repository_file(root: Path, raw: str, *, parent: str) -> Path:
    expected_parent = (root / parent).resolve()
    candidate = root / raw
    path = candidate.resolve()
    if not path.is_relative_to(expected_parent) or candidate.is_symlink() or not path.is_file():
        raise EvaluationConfigError(f"referenced file must be regular and under {parent}: {raw}")
    return path


def _load_gate2_artifact(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationConfigError(f"invalid Gate 2 artifact {path}: {exc}") from exc
    expected = {
        "artifact_id": "gate-2-evidence",
        "task_id": "gate-2-harness",
        "gate_id": "gate-2",
        "status": "passed",
        "evidence_label": "deterministic_mock_engineering_evidence",
        "scientific_results": False,
        "live_calls": 0,
    }
    if not isinstance(payload, dict) or any(
        payload.get(key) != value for key, value in expected.items()
    ):
        raise EvaluationConfigError("Issue #14 requires the accepted offline Gate 2 evidence")
    matrix = payload.get("matrix")
    if not isinstance(matrix, dict):
        raise EvaluationConfigError("Gate 2 artifact is missing its matrix evidence")
    if tuple(matrix.get("formation_conditions", ())) != FORMATION_CONDITIONS:
        raise EvaluationConfigError("Gate 2 formation order differs from the frozen matrix")
    if tuple(matrix.get("intervention_conditions", ())) != INTERVENTION_CONDITIONS:
        raise EvaluationConfigError("Gate 2 intervention order differs from the frozen matrix")


def _validate_experiment(
    kind: DesignKind,
    spec: ExperimentSpec,
    config: OfflineEvaluationConfig,
) -> None:
    design = spec.design
    if design is None or design.kind != kind:
        raise EvaluationConfigError(f"{kind} experiment must contain its frozen design")
    if tuple(design.formation_conditions) != FORMATION_CONDITIONS:
        raise EvaluationConfigError(f"{kind} formation order differs from the Gate 2 contract")
    if tuple(design.intervention_conditions) != INTERVENTION_CONDITIONS:
        raise EvaluationConfigError(f"{kind} intervention order differs from the Gate 2 contract")
    expected = (
        config.expected_pilot_trajectories
        if kind == "pilot"
        else config.expected_primary_trajectories
    )
    if design.expected_trajectories != expected:
        raise EvaluationConfigError(f"{kind} trajectory count differs from the frozen target")
    budget = config.budgets[kind]
    if budget.max_trajectories != expected:
        raise EvaluationConfigError(f"{kind} budget must cover exactly the frozen assignments")
    if budget.max_model_calls != design.limits.max_model_calls:
        raise EvaluationConfigError(f"{kind} call budget differs from the experiment freeze")
    if budget.max_wall_clock_seconds != design.limits.max_wall_clock_hours * 3600:
        raise EvaluationConfigError(f"{kind} time budget differs from the experiment freeze")
    bound_families = {item.family for item in config.model_bindings}
    if not set(design.model_families).issubset(bound_families):
        raise EvaluationConfigError(f"{kind} design references an unbound model family")


def load_evaluation_config(path: Path, *, project_root: Path) -> LoadedEvaluationConfig:
    """Load the one offline config and validate all references before scheduling."""

    root = project_root.resolve()
    allowed = (root / "configs/evaluation").resolve()
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(allowed) or not resolved.is_file():
        raise EvaluationConfigError(
            "Issue #14 config must be a regular file under configs/evaluation"
        )
    try:
        config = OfflineEvaluationConfig.model_validate(load_yaml(resolved))
    except (ConfigError, OSError, ValueError) as exc:
        raise EvaluationConfigError(f"invalid Issue #14 config {path}: {exc}") from exc

    experiments: dict[DesignKind, ExperimentSpec] = {}
    experiment_hashes: dict[DesignKind, str] = {}
    for kind, raw in config.experiment_configs.items():
        experiment_path = _regular_repository_file(root, raw, parent="configs/experiments")
        try:
            spec = ExperimentSpec.model_validate(load_yaml(experiment_path))
        except (ConfigError, OSError, ValueError) as exc:
            raise EvaluationConfigError(f"invalid {kind} experiment {raw}: {exc}") from exc
        _validate_experiment(kind, spec, config)
        experiments[kind] = spec
        experiment_hashes[kind] = sha256_file(experiment_path)

    adapter_hashes: dict[str, str] = {}
    for binding in config.model_bindings:
        adapter_path = _regular_repository_file(
            root,
            binding.adapter_config_path,
            parent="configs/models",
        )
        try:
            adapter = load_adapter_config(adapter_path)
        except ValueError as exc:
            raise EvaluationConfigError(
                f"invalid adapter config for {binding.family}: {exc}"
            ) from exc
        if adapter.live_calls_enabled:
            raise EvaluationConfigError("offline Issue #14 rejects live-enabled adapters")
        adapter_hashes[binding.family] = sha256_file(adapter_path)

    gate2_path = _regular_repository_file(
        root,
        config.gate2_artifact_path,
        parent="artifacts/orchestration",
    )
    _load_gate2_artifact(gate2_path)
    return LoadedEvaluationConfig(
        config=config,
        config_sha256=sha256_file(resolved),
        source_path=resolved,
        project_root=root,
        experiments=experiments,
        experiment_sha256=experiment_hashes,
        adapter_config_sha256=adapter_hashes,
        gate2_artifact_sha256=sha256_file(gate2_path),
    )
