"""Fail-closed loading of the frozen world and matched forty-day trajectory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.data.contracts import DatasetManifest, PartitionManifest
from affective_belief_persistence.determinism import sha256_file, sha256_value
from affective_belief_persistence.schemas import FormationCondition, ModelConfig
from affective_belief_persistence.world import ActionOption, Consequence, Event, ResourceBudget

Sha256 = str
PartitionPurpose = Literal["training", "evaluation"]

FORMATION_PATHS: dict[FormationCondition, str] = {
    "neutral_connection": "data/formation/neutral.jsonl",
    "romantic_prompt": "data/formation/romantic_prompt.jsonl",
    "shared_memory": "data/formation/shared_memory.jsonl",
    "memory_plus_investment": "data/formation/memory_investment.jsonl",
}
SHOCK_PATH = "data/held_out/reality_shock.jsonl"
ADAPTATION_PATH = "data/held_out/adaptation.jsonl"
REQUIRED_WORLD_PATHS = frozenset(
    {
        "data/world/characters.yaml",
        "data/world/goals.yaml",
        "data/world/action-catalog.yaml",
    }
)


def _load_yaml(path: Path) -> dict[str, Any]:
    # Delayed to keep schema generation free of config -> schemas -> simulation
    # import cycles.
    from affective_belief_persistence.config import load_yaml

    return load_yaml(path)


class ScenarioLoadError(ValueError):
    """Frozen simulation inputs failed provenance or split validation."""


class ProtectedSplitError(ScenarioLoadError):
    """Protected evaluation content was requested for a training purpose."""


class SimulationConfig(BaseModel):
    """Strict, versioned configuration for one frozen-condition trajectory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    simulation_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    version: str = Field(min_length=1)
    dataset_manifest_path: str = Field(min_length=1)
    expected_dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    world_artifact_path: str = Field(min_length=1)
    formation_condition: FormationCondition
    seed: int = Field(ge=0, le=2**63 - 1)
    model_config_path: str = Field(min_length=1)
    first_day: Literal[1] = 1
    last_day: Literal[40] = 40
    daily_budget_id: str = Field(min_length=1)
    checkpoint_cadence_steps: int = Field(ge=1, le=40)
    held_out_evaluation_authorized: Literal[True]
    prompt_version: str = Field(min_length=1)
    decision_schema_version: Literal["1.0"] = "1.0"

    @model_validator(mode="after")
    def validate_paths(self) -> SimulationConfig:
        for name, raw in {
            "dataset_manifest_path": self.dataset_manifest_path,
            "world_artifact_path": self.world_artifact_path,
            "model_config_path": self.model_config_path,
        }.items():
            candidate = Path(raw)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError(f"{name} must be a non-traversing repository-relative path")
        return self


class VerifiedDataset(BaseModel):
    """Manifest metadata after every declared partition byte hash has passed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: DatasetManifest
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_partition_paths: tuple[str, ...]


class LoadedScenario(BaseModel):
    """The only legal full trajectory: selected formation plus held-out evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    config: SimulationConfig
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest: DatasetManifest
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    world_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    world_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_settings: ModelConfig
    model_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget: ResourceBudget
    actions: tuple[ActionOption, ...]
    consequences: tuple[Consequence, ...]
    events: tuple[Event, ...]
    scenario_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_trajectory(self) -> LoadedScenario:
        if [event.day for event in self.events] != list(range(1, 41)):
            raise ValueError(
                "loaded trajectory must contain exactly one event for days 1 through 40"
            )
        if any(
            event.condition_variant.formation_condition != self.config.formation_condition
            for event in self.events
        ):
            raise ValueError("loaded trajectory contains a different formation condition")
        expected_hash = _scenario_hash_payload(
            config=self.config,
            manifest=self.manifest,
            world_input_sha256=self.world_input_sha256,
            model_config_sha256=self.model_config_sha256,
            budget=self.budget,
            actions=self.actions,
            consequences=self.consequences,
            events=self.events,
        )
        if self.scenario_sha256 != sha256_value(expected_hash):
            raise ValueError("scenario hash does not match its canonical inputs")
        return self


def _resolve(root: Path, relative: str, *, expected_parent: str | None = None) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ScenarioLoadError(f"input path must be repository-relative: {relative}")
    unresolved = root / candidate
    cursor = root
    for part in candidate.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ScenarioLoadError(f"input path cannot traverse a symlink: {relative}")
    resolved = unresolved.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ScenarioLoadError(f"input path escapes repository root: {relative}")
    if expected_parent is not None:
        allowed = (root / expected_parent).resolve()
        if not resolved.is_relative_to(allowed):
            raise ScenarioLoadError(f"input path is outside {expected_parent}: {relative}")
    if not resolved.is_file():
        raise ScenarioLoadError(f"input must be an existing regular file: {relative}")
    return resolved


def load_simulation_config(path: Path, *, project_root: Path) -> SimulationConfig:
    """Load a strict simulation YAML from ``configs/scenarios``."""

    root = project_root.resolve()
    if path.is_symlink():
        raise ScenarioLoadError("simulation config cannot be a symlink")
    resolved = path.resolve()
    allowed = (root / "configs/scenarios").resolve()
    if not resolved.is_relative_to(allowed) or resolved.is_symlink():
        raise ScenarioLoadError("simulation config must be a regular file under configs/scenarios")
    try:
        return SimulationConfig.model_validate(_load_yaml(resolved))
    except (OSError, ValueError) as exc:
        raise ScenarioLoadError(f"invalid simulation config {path}: {exc}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ScenarioLoadError(f"JSON input exceeds 2 MiB: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioLoadError(f"invalid JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ScenarioLoadError(f"JSON input must be an object: {path}")
    return value


def verify_world_artifact(root: Path, config: SimulationConfig) -> tuple[str, str]:
    """Verify every frozen ``data/world`` file pinned by the accepted Issue 7 artifact."""

    artifact_path = _resolve(root, config.world_artifact_path, expected_parent="artifacts/data")
    artifact = _load_json(artifact_path)
    if (
        artifact.get("artifact_id") != "issue-7-data-contracts"
        or artifact.get("status") != "accepted"
    ):
        raise ScenarioLoadError("world artifact is not the accepted Issue 7 data contract")
    entries = artifact.get("artifacts")
    if not isinstance(entries, list):
        raise ScenarioLoadError("world artifact is missing its artifact list")
    declared: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ScenarioLoadError("world artifact entries must be objects")
        relative = entry.get("path")
        digest = entry.get("sha256")
        if isinstance(relative, str) and relative.startswith("data/world/"):
            if relative in declared or not isinstance(digest, str):
                raise ScenarioLoadError("world artifact contains an invalid or duplicate path")
            declared[relative] = digest
    if set(declared) != REQUIRED_WORLD_PATHS:
        raise ScenarioLoadError("world artifact must pin exactly the three frozen world inputs")
    for relative, expected in sorted(declared.items()):
        actual = sha256_file(_resolve(root, relative, expected_parent="data/world"))
        if actual != expected:
            raise ScenarioLoadError(f"frozen world input hash mismatch: {relative}")
    world_digest = sha256_value(dict(sorted(declared.items())))
    return sha256_file(artifact_path), world_digest


def verify_dataset(root: Path, config: SimulationConfig) -> VerifiedDataset:
    """Validate the manifest, every partition byte hash, and the frozen dataset hash."""

    manifest_path = _resolve(root, config.dataset_manifest_path, expected_parent="data/manifests")
    try:
        manifest = DatasetManifest.model_validate(_load_json(manifest_path))
    except ValueError as exc:
        raise ScenarioLoadError(f"dataset manifest contract failed: {exc}") from exc
    if manifest.dataset_sha256 != config.expected_dataset_sha256:
        raise ScenarioLoadError("dataset manifest does not match expected_dataset_sha256")
    paths = [partition.path for partition in manifest.partitions]
    if len(paths) != len(set(paths)):
        raise ScenarioLoadError("dataset manifest contains duplicate partition paths")
    for partition in manifest.partitions:
        path = _resolve(root, partition.path, expected_parent="data")
        if sha256_file(path) != partition.sha256:
            raise ScenarioLoadError(f"dataset partition hash mismatch: {partition.path}")
        if partition.role == "held_out" and not partition.protected_from_training:
            raise ScenarioLoadError(f"held-out partition is not protected: {partition.path}")
        if partition.role != "held_out" and partition.protected_from_training:
            raise ScenarioLoadError(
                f"non-held-out partition is unexpectedly protected: {partition.path}"
            )
    recomputed = sha256_value(
        {
            item.path: item.sha256
            for item in sorted(manifest.partitions, key=lambda item: item.path)
            if item.role != "smoke"
        }
    )
    if recomputed != manifest.dataset_sha256 or recomputed != config.expected_dataset_sha256:
        raise ScenarioLoadError("recomputed frozen dataset SHA does not match the manifest")
    return VerifiedDataset(
        manifest=manifest,
        manifest_sha256=sha256_file(manifest_path),
        verified_partition_paths=tuple(sorted(paths)),
    )


def _partition(manifest: DatasetManifest, path: str) -> PartitionManifest:
    matches = [item for item in manifest.partitions if item.path == path]
    if len(matches) != 1:
        raise ScenarioLoadError(f"manifest must declare partition exactly once: {path}")
    return matches[0]


def load_partition_events(
    root: Path,
    verified: VerifiedDataset,
    partition_path: str,
    *,
    purpose: PartitionPurpose,
    held_out_evaluation_authorized: bool = False,
) -> tuple[Event, ...]:
    """Parse a verified partition while enforcing its protected-split boundary."""

    partition = _partition(verified.manifest, partition_path)
    if partition.protected_from_training and purpose != "evaluation":
        raise ProtectedSplitError(
            f"protected partition cannot be loaded for training: {partition_path}"
        )
    if partition.protected_from_training and not held_out_evaluation_authorized:
        raise ProtectedSplitError(
            f"protected partition lacks evaluation authorization: {partition_path}"
        )
    path = _resolve(root, partition_path, expected_parent="data")
    events: list[Event] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                raise ScenarioLoadError(f"blank JSONL record in {partition_path}:{line_number}")
            events.append(Event.model_validate_json(line))
    except (OSError, ValueError) as exc:
        if isinstance(exc, ScenarioLoadError):
            raise
        raise ScenarioLoadError(f"invalid event partition {partition_path}: {exc}") from exc
    if len(events) != partition.record_count:
        raise ScenarioLoadError(f"partition record count mismatch: {partition_path}")
    if not events or min(item.day for item in events) != partition.first_day:
        raise ScenarioLoadError(f"partition first_day mismatch: {partition_path}")
    if max(item.day for item in events) != partition.last_day:
        raise ScenarioLoadError(f"partition last_day mismatch: {partition_path}")
    return tuple(events)


def _load_catalog(
    root: Path, config: SimulationConfig
) -> tuple[ResourceBudget, tuple[ActionOption, ...], tuple[Consequence, ...]]:
    catalog_path = _resolve(root, "data/world/action-catalog.yaml", expected_parent="data/world")
    try:
        catalog = _load_yaml(catalog_path)
        budgets = tuple(ResourceBudget.model_validate(item) for item in catalog["resource_budgets"])
        actions = tuple(ActionOption.model_validate(item) for item in catalog["actions"])
        consequences = tuple(Consequence.model_validate(item) for item in catalog["consequences"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ScenarioLoadError(f"invalid frozen action catalog: {exc}") from exc
    selected = [item for item in budgets if item.resource_budget_id == config.daily_budget_id]
    if len(selected) != 1 or selected[0].daily_total != 10 or selected[0].carry_over:
        raise ScenarioLoadError("daily budget must be the unique non-carrying 10-point budget")
    consequence_by_id = {item.consequence_id: item for item in consequences}
    if len(consequence_by_id) != len(consequences):
        raise ScenarioLoadError("consequence IDs must be unique")
    if len({item.action_id for item in actions}) != len(actions):
        raise ScenarioLoadError("action IDs must be unique")
    for action in actions:
        consequence = consequence_by_id.get(action.consequence_id)
        if consequence is None or consequence.resource_delta != -action.cost:
            raise ScenarioLoadError(f"action does not conserve resources: {action.action_id}")
    return selected[0], actions, consequences


def _scenario_hash_payload(
    *,
    config: SimulationConfig,
    manifest: DatasetManifest,
    world_input_sha256: str,
    model_config_sha256: str,
    budget: ResourceBudget,
    actions: tuple[ActionOption, ...],
    consequences: tuple[Consequence, ...],
    events: tuple[Event, ...],
) -> dict[str, object]:
    return {
        "actions": [item.model_dump(mode="json") for item in actions],
        "budget": budget.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
        "consequences": [item.model_dump(mode="json") for item in consequences],
        "dataset_sha256": manifest.dataset_sha256,
        "events": [item.model_dump(mode="json") for item in events],
        "model_config_sha256": model_config_sha256,
        "world_input_sha256": world_input_sha256,
    }


def load_scenario(config_path: Path, *, project_root: Path) -> LoadedScenario:
    """Load the selected 1..25 formation and authorized protected 26..40 evaluation."""

    root = project_root.resolve()
    config = load_simulation_config(config_path, project_root=root)
    world_artifact_sha256, world_input_sha256 = verify_world_artifact(root, config)
    verified = verify_dataset(root, config)
    formation = load_partition_events(
        root,
        verified,
        FORMATION_PATHS[config.formation_condition],
        purpose="training",
    )
    shock = load_partition_events(
        root,
        verified,
        SHOCK_PATH,
        purpose="evaluation",
        held_out_evaluation_authorized=config.held_out_evaluation_authorized,
    )
    adaptation = load_partition_events(
        root,
        verified,
        ADAPTATION_PATH,
        purpose="evaluation",
        held_out_evaluation_authorized=config.held_out_evaluation_authorized,
    )
    condition = config.formation_condition
    selected_shock = tuple(
        event for event in shock if event.condition_variant.formation_condition == condition
    )
    selected_adaptation = tuple(
        event for event in adaptation if event.condition_variant.formation_condition == condition
    )
    events = (*formation, *selected_shock, *selected_adaptation)
    if [event.day for event in formation] != list(range(1, 26)):
        raise ScenarioLoadError("selected formation partition must contain days 1 through 25")
    if [event.day for event in selected_shock] != [26]:
        raise ScenarioLoadError("selected held-out shock must contain only day 26")
    if [event.day for event in selected_adaptation] != list(range(27, 41)):
        raise ScenarioLoadError("selected held-out adaptation must contain days 27 through 40")
    budget, actions, consequences = _load_catalog(root, config)
    model_path = _resolve(root, config.model_config_path, expected_parent="configs/models")
    try:
        model_config = ModelConfig.model_validate(_load_yaml(model_path))
    except ValueError as exc:
        raise ScenarioLoadError(f"invalid model config: {exc}") from exc
    model_config_sha256 = sha256_file(model_path)
    config_sha256 = sha256_value(config)
    payload = _scenario_hash_payload(
        config=config,
        manifest=verified.manifest,
        world_input_sha256=world_input_sha256,
        model_config_sha256=model_config_sha256,
        budget=budget,
        actions=actions,
        consequences=consequences,
        events=events,
    )
    return LoadedScenario(
        config=config,
        config_sha256=config_sha256,
        manifest=verified.manifest,
        manifest_sha256=verified.manifest_sha256,
        world_artifact_sha256=world_artifact_sha256,
        world_input_sha256=world_input_sha256,
        model_settings=model_config,
        model_config_sha256=model_config_sha256,
        budget=budget,
        actions=actions,
        consequences=consequences,
        events=events,
        scenario_sha256=sha256_value(payload),
    )
