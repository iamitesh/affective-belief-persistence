"""Safe YAML loading and explicit component composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.schemas import (
    AgentConfig,
    EvaluationConfig,
    ExperimentSpec,
    ModelConfig,
    ResolvedRunConfig,
    ScenarioConfig,
    WorkflowConfig,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class ConfigError(ValueError):
    """Configuration cannot be loaded safely or consistently."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConfigError("configuration keys must be strings")
        if key in mapping:
            raise ConfigError(f"duplicate configuration key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True)
class LoadedRunConfig:
    resolved: ResolvedRunConfig
    config_sha256: str
    source_path: Path
    project_root: Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise ConfigError("could not find project root containing pyproject.toml")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"configuration file does not exist: {path}")
    if path.stat().st_size > 1024 * 1024:
        raise ConfigError(f"configuration file exceeds 1 MiB: {path}")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration root must be a mapping: {path}")
    return data


def parse_yaml(path: Path, model: type[ModelT]) -> ModelT:
    return model.model_validate(load_yaml(path))


def _component_path(config_root: Path, reference: str) -> Path:
    candidate = Path(reference)
    if candidate.is_absolute():
        raise ConfigError(f"component path must be relative: {reference}")
    resolved = (config_root / candidate).resolve()
    if not resolved.is_relative_to(config_root.resolve()):
        raise ConfigError(f"component path escapes the config root: {reference}")
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def load_run_config(path: Path, *, project_root: Path | None = None) -> LoadedRunConfig:
    source_path = path.resolve()
    root = (project_root or find_project_root(source_path)).resolve()
    config_root = (root / "configs").resolve()
    if not source_path.is_relative_to(config_root):
        raise ConfigError("experiment configuration must be located under configs/")

    spec = parse_yaml(source_path, ExperimentSpec)
    references = spec.components
    component_paths = {
        "agent": _component_path(config_root, references.agent),
        "model": _component_path(config_root, references.model),
        "scenario": _component_path(config_root, references.scenario),
        "workflow": _component_path(config_root, references.workflow),
        "evaluation": _component_path(config_root, references.evaluation),
    }
    resolved = ResolvedRunConfig(
        schema_version="1.0",
        experiment_id=spec.experiment_id,
        seed=spec.seed,
        prompt_version=spec.prompt_version,
        dataset_version=spec.dataset_version,
        metric_version=spec.metric_version,
        formation_condition=spec.formation_condition,
        separation_condition=spec.separation_condition,
        intervention_condition=spec.intervention_condition,
        agent=parse_yaml(component_paths["agent"], AgentConfig),
        model=parse_yaml(component_paths["model"], ModelConfig),
        scenario=parse_yaml(component_paths["scenario"], ScenarioConfig),
        workflow=parse_yaml(component_paths["workflow"], WorkflowConfig),
        evaluation=parse_yaml(component_paths["evaluation"], EvaluationConfig),
        source_paths={
            "experiment": _relative(source_path, root),
            **{name: _relative(component, root) for name, component in component_paths.items()},
        },
    )
    return LoadedRunConfig(
        resolved=resolved,
        config_sha256=sha256_value(resolved),
        source_path=source_path,
        project_root=root,
    )
