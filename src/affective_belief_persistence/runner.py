"""Offline foundation runner and manifest-based reproduction."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from affective_belief_persistence.config import (
    ConfigError,
    LoadedRunConfig,
    find_project_root,
    load_run_config,
)
from affective_belief_persistence.determinism import canonical_json, sha256_file, sha256_value
from affective_belief_persistence.models.mock import DeterministicMockModel
from affective_belief_persistence.provenance import collect_code_state, collect_environment
from affective_belief_persistence.schemas import (
    ArtifactRecord,
    DecisionRecord,
    DecisionRequest,
    ExperimentProvenance,
    ModelProvenance,
    RunManifest,
    UsageRecord,
    ValidationRecord,
)


class RunnerError(RuntimeError):
    """An experiment cannot execute without violating foundation guarantees."""


class ReproductionError(RunnerError):
    """A replay did not reproduce the recorded deterministic artifacts."""


def _prepare_output(path: Path) -> Path:
    output = path.resolve()
    if output.is_symlink():
        raise RunnerError(f"output directory cannot be a symlink: {path}")
    if output.exists() and any(output.iterdir()):
        raise RunnerError(f"output directory must be empty: {path}")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _artifact(
    path: Path, output: Path, *, logical_name: str, role: str, media_type: str
) -> ArtifactRecord:
    if path.is_symlink() or not path.resolve().is_relative_to(output.resolve()):
        raise RunnerError(f"artifact path escapes the run directory: {path}")
    return ArtifactRecord(
        logical_name=logical_name,
        path=path.relative_to(output).as_posix(),
        role=role,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        media_type=media_type,
    )


def _decision_records(config: LoadedRunConfig) -> list[DecisionRecord]:
    resolved = config.resolved
    model = DeterministicMockModel(resolved.model)
    records: list[DecisionRecord] = []
    for step in resolved.scenario.steps:
        request = DecisionRequest(
            schema_version="1.0",
            request_id=f"{resolved.scenario.scenario_id}:{step.event_id}:day-{step.day}",
            event_id=step.event_id,
            day=step.day,
            facts=step.facts,
            action_points=step.action_points,
            available_actions=step.available_actions,
            retrieved_memory_ids=[],
            beliefs={},
        )
        decision = model.decide(request, seed=resolved.seed)
        allowed = {action.action_id: action.cost for action in step.available_actions}
        if decision.chosen_action not in allowed:
            raise RunnerError(f"mock model selected unavailable action: {decision.chosen_action}")
        if decision.resources_spent != allowed[decision.chosen_action]:
            raise RunnerError("mock model returned a resource cost that does not match its action")
        records.append(
            DecisionRecord(
                schema_version="1.0",
                event_id=step.event_id,
                day=step.day,
                decision=decision,
            )
        )
    return records


def _result_set_sha256(artifacts: list[ArtifactRecord]) -> str:
    stable = [
        {
            "path": artifact.path,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
        }
        for artifact in sorted(artifacts, key=lambda item: item.path)
    ]
    return sha256_value(stable)


def execute_dry_run(config_path: Path, output_path: Path) -> RunManifest:
    loaded = load_run_config(config_path)
    output = _prepare_output(output_path)
    code_state = collect_code_state(loaded.project_root)
    environment = collect_environment()
    started_at = datetime.now(UTC)
    monotonic_start = time.monotonic()

    resolved_path = output / "resolved-config.json"
    _write_atomic(
        resolved_path,
        canonical_json(
            {
                "config_sha256": loaded.config_sha256,
                "resolved": loaded.resolved.model_dump(mode="json"),
            }
        )
        + "\n",
    )

    records = _decision_records(loaded)
    results_path = output / "results.jsonl"
    _write_atomic(
        results_path,
        "".join(canonical_json(record) + "\n" for record in records),
    )

    artifacts = [
        _artifact(
            resolved_path,
            output,
            logical_name="resolved_config",
            role="configuration",
            media_type="application/json",
        ),
        _artifact(
            results_path,
            output,
            logical_name="mock_decisions",
            role="scientific_output",
            media_type="application/x-ndjson",
        ),
    ]
    result_set_sha256 = _result_set_sha256(artifacts)
    completed_at = datetime.now(UTC)
    runtime_seconds = max(0.0, time.monotonic() - monotonic_start)
    resolved = loaded.resolved
    source_config = resolved.source_paths["experiment"]
    run_id = f"{resolved.experiment_id}-{loaded.config_sha256[:12]}-seed-{resolved.seed}"
    input_tokens = sum(max(1, len(canonical_json(step)) // 4) for step in resolved.scenario.steps)
    output_tokens = sum(max(1, len(canonical_json(record)) // 4) for record in records)
    manifest = RunManifest(
        schema_version="1.0",
        run_id=run_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        runtime_seconds=runtime_seconds,
        code=code_state,
        environment=environment,
        experiment=ExperimentProvenance(
            experiment_id=resolved.experiment_id,
            source_config=source_config,
            config_sha256=loaded.config_sha256,
            resolved_config_artifact="resolved-config.json",
            seed=resolved.seed,
            scenario_id=resolved.scenario.scenario_id,
            scenario_version=resolved.scenario.version,
            prompt_version=resolved.prompt_version,
            dataset_version=resolved.dataset_version,
            metric_version=resolved.metric_version,
            formation_condition=resolved.formation_condition,
            separation_condition=resolved.separation_condition,
            intervention_condition=resolved.intervention_condition,
        ),
        model=ModelProvenance(
            provider=resolved.model.provider,
            model_id=resolved.model.model_id,
            revision=resolved.model.revision,
            adapter_id=None,
            inference_parameters={
                "temperature": resolved.model.temperature,
                "max_output_tokens": resolved.model.max_output_tokens,
            },
        ),
        artifacts=artifacts,
        result_set_sha256=result_set_sha256,
        usage=UsageRecord(
            model_calls=len(records),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=0.0,
        ),
        validation=ValidationRecord(
            passed=True,
            checks=[
                "configuration_valid",
                "structured_decisions_valid",
                "actions_available",
                "resource_costs_match",
                "artifacts_hashed",
                "offline_only",
            ],
            failures=[],
        ),
    )
    manifest_path = output / "run-manifest.json"
    _write_atomic(manifest_path, canonical_json(manifest) + "\n")
    return manifest


def load_manifest(path: Path) -> RunManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(f"could not load run manifest {path}: {exc}") from exc
    return RunManifest.model_validate(data)


def reproduce_run(manifest_path: Path, output_path: Path) -> RunManifest:
    recorded = load_manifest(manifest_path)
    try:
        root = find_project_root(manifest_path)
    except ConfigError:
        root = find_project_root()
    config_path = root / recorded.experiment.source_config
    reproduced = execute_dry_run(config_path, output_path)
    failures: list[str] = []
    if reproduced.experiment.config_sha256 != recorded.experiment.config_sha256:
        failures.append("resolved configuration hash differs")
    if reproduced.result_set_sha256 != recorded.result_set_sha256:
        failures.append("deterministic result-set hash differs")
    if failures:
        raise ReproductionError("; ".join(failures))
    return reproduced
