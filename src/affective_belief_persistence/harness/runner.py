"""Composite Gate 2 runner, checkpointing, replay, and matrix materialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affective_belief_persistence.determinism import sha256_file, sha256_value
from affective_belief_persistence.harness.config import Gate2HarnessConfig, LoadedHarnessConfig
from affective_belief_persistence.harness.contracts import (
    FORMATION_CONDITIONS,
    INTERVENTION_CONDITIONS,
    CellComponentHashes,
    ConsumedArtifact,
    FormationCondition,
    HarnessCellIdentity,
    HarnessCellManifest,
    HarnessCheckpoint,
    HarnessRunManifest,
    HarnessStepEvidence,
    InterventionCondition,
)
from affective_belief_persistence.harness.model import (
    Gate2DeterministicModel,
    HarnessMemoryBridge,
)
from affective_belief_persistence.harness.scenario import ScenarioFactory
from affective_belief_persistence.interventions.audit import audit_record
from affective_belief_persistence.interventions.contracts import InstructionDirective
from affective_belief_persistence.interventions.runtime import (
    InterventionCheckpoint,
    InterventionRuntime,
    load_intervention_spec,
)
from affective_belief_persistence.memory.integration import MemoryRuntime
from affective_belief_persistence.memory.scoring import load_memory_config
from affective_belief_persistence.models.prompt_builder import PromptBundle
from affective_belief_persistence.simulation.engine import SimulationEngine, initial_state
from affective_belief_persistence.simulation.scenario_loader import LoadedScenario
from affective_belief_persistence.simulation.state import (
    SimulationCheckpoint,
    SimulationResult,
    SimulationStepRecord,
)


class HarnessError(RuntimeError):
    """Gate 2 cannot continue without violating a composite invariant."""


class CompositeCheckpointError(HarnessError):
    """A component checkpoint is corrupt, torn, swapped, or stale."""


@dataclass(frozen=True)
class CompositeCheckpointBundle:
    """In-memory component payloads bound by one hash-protected pointer."""

    pointer: HarnessCheckpoint
    simulation: SimulationCheckpoint
    intervention: InterventionCheckpoint
    evidence: tuple[HarnessStepEvidence, ...]


@dataclass
class CellExecution:
    """Mutable runtime for one opaque Gate 2 factorial cell."""

    cell: HarnessCellIdentity
    scenario: LoadedScenario
    runtime: InterventionRuntime
    bridge: HarnessMemoryBridge
    model: Gate2DeterministicModel
    engine: SimulationEngine
    evidence: list[HarnessStepEvidence] = field(default_factory=list)

    def step(self) -> HarnessStepEvidence:
        """Run one transaction and roll back every sidecar if any stage fails."""

        state_before = self.engine.state
        runtime_before = self.runtime.snapshot(state_before)
        model_before = self.model.state()
        evidence_before = tuple(self.evidence)
        try:
            record = self.engine.step()
            evidence = _evidence_for_step(self, record)
        except Exception:
            self.runtime.abort_pending_step()
            restored = InterventionRuntime.restore(runtime_before, state_before)
            self.runtime = restored
            self.bridge.replace_runtime(restored)
            self.model.restore_state(model_before)
            self.engine.memory = self.bridge
            self.engine.state = state_before
            self.evidence = list(evidence_before)
            raise
        self.evidence.append(evidence)
        return evidence

    def run_through(self, day: int = 40) -> SimulationResult:
        if not self.engine.state.next_day <= day + 1 <= 41:
            raise HarnessError("requested end day precedes the current composite state")
        while self.engine.state.next_day <= day:
            self.step()
        return SimulationResult.from_state(self.engine.state)


def _artifact_payload(path: Path, expected_id: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise HarnessError(f"consumed artifact must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"invalid consumed artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HarnessError(f"consumed artifact is not a JSON object: {path}")
    if payload.get("artifact_id") != expected_id or payload.get("status") != "accepted":
        raise HarnessError(f"consumed artifact is not accepted {expected_id}: {path}")
    return payload


def verify_consumed_artifacts(
    config: Gate2HarnessConfig,
    *,
    project_root: Path,
) -> tuple[ConsumedArtifact, ...]:
    root = project_root.resolve()
    verified: list[ConsumedArtifact] = []
    for item in config.consumed_artifacts:
        path = (root / item.path).resolve()
        if not path.is_relative_to(root):
            raise HarnessError(f"consumed artifact escapes project root: {item.path}")
        _artifact_payload(path, item.artifact_id)
        verified.append(
            ConsumedArtifact(
                artifact_id=item.artifact_id,  # type: ignore[arg-type]
                path=item.path,
                sha256=sha256_file(path),
            )
        )
    return tuple(verified)


def _prompt_bundle_sha256(project_root: Path, prompt_directory: str) -> str:
    directory = (project_root / prompt_directory).resolve()
    if not directory.is_relative_to(project_root.resolve()) or directory.is_symlink():
        raise HarnessError("prompt directory escapes the project root or is a symlink")
    paths = tuple(directory / name for name in ("v1.action.md", "v1.language.md", "v1.repair.md"))
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise HarnessError("Gate 2 prompt bundle is incomplete")
    return sha256_value({path.name: sha256_file(path) for path in paths})


def _intervention_ledger_sha256(runtime: InterventionRuntime) -> str:
    return sha256_value([record.record_sha256 for record in runtime.records])


def start_cell(
    *,
    formation: FormationCondition,
    intervention: InterventionCondition,
    loaded: LoadedHarnessConfig,
    project_root: Path,
) -> CellExecution:
    config = loaded.config
    root = project_root.resolve()
    scenario_path = root / config.base_scenario_path
    scenario = ScenarioFactory(root, scenario_path, config.engineering_seed).build(formation)
    spec_path = root / config.intervention_configs[intervention]
    spec = load_intervention_spec(spec_path)
    if spec.condition != intervention:
        raise HarnessError("intervention filename mapping disagrees with its strict config")
    memory_path = root / config.memory_config_path
    memory = MemoryRuntime(load_memory_config(memory_path))
    instruction = (
        (
            InstructionDirective(
                instruction_id=config.instruction.instruction_id,
                text=config.instruction.text,
            ),
        )
        if formation in config.instruction.active_for_formations
        else ()
    )
    runtime = InterventionRuntime(spec, memory, instructions=instruction)
    bridge = HarnessMemoryBridge(runtime)
    prompt_dir = root / config.prompt_directory
    prompts = PromptBundle.load(prompt_dir, version=config.prompt_version)
    model_path = root / config.model_config_path
    artifact_hashes = {
        item.artifact_id: sha256_file(root / item.path) for item in config.consumed_artifacts
    }
    components = CellComponentHashes(
        harness_config_sha256=loaded.config_sha256,
        dataset_sha256=scenario.manifest.dataset_sha256,
        dataset_manifest_sha256=scenario.manifest_sha256,
        world_input_sha256=scenario.world_input_sha256,
        scenario_sha256=scenario.scenario_sha256,
        simulation_config_sha256=scenario.config_sha256,
        memory_config_sha256=sha256_file(memory_path),
        intervention_config_sha256=sha256_file(spec_path),
        model_config_sha256=sha256_file(model_path),
        prompt_bundle_sha256=_prompt_bundle_sha256(root, config.prompt_directory),
        simulation_artifact_sha256=artifact_hashes["issue-9-simulation-harness"],
        memory_artifact_sha256=artifact_hashes["issue-10-memory-subsystem"],
        intervention_artifact_sha256=artifact_hashes["issue-11-intervention-engine"],
        model_runner_artifact_sha256=artifact_hashes["issue-12-model-runner"],
    )
    cell = HarnessCellIdentity.create(
        formation_condition=formation,
        intervention_condition=intervention,
        engineering_seed=config.engineering_seed,
        components=components,
    )
    model = Gate2DeterministicModel(
        scenario=scenario,
        bridge=bridge,
        prompts=prompts,
        model_config_sha256=components.model_config_sha256,
    )
    engine = SimulationEngine(scenario, model, memory=bridge)
    return CellExecution(
        cell=cell,
        scenario=scenario,
        runtime=runtime,
        bridge=bridge,
        model=model,
        engine=engine,
    )


def _evidence_for_step(
    execution: CellExecution,
    record: SimulationStepRecord,
) -> HarnessStepEvidence:
    trace = execution.model.trace_for_request(record.request_id)
    context = execution.bridge.latest_context
    event = execution.bridge.latest_event
    if context is None or event is None:
        raise HarnessError("completed simulation step lacks captured pre-action context")
    if event.event_id != record.event_id or event.day != record.day:
        raise HarnessError("captured Gate 2 event differs from simulation evidence")
    if tuple(item.memory_id for item in trace.selected_memories) != tuple(
        record.decision.retrieved_memory_ids
    ):
        raise HarnessError("rich selected-memory evidence differs from the committed decision")
    memory_checkpoint = execution.runtime.memory.checkpoint()
    intervention_record = execution.runtime.records[-1] if execution.runtime.records else None
    if record.day >= 30 and intervention_record is None:
        raise HarnessError("post-intervention step lacks an append-only intervention record")
    if record.day < 30 and intervention_record is not None:
        raise HarnessError("intervention record appeared before frozen day 30")
    if (
        record.day == 30
        and intervention_record is not None
        and intervention_record.intervention_condition in {"memory_blocking", "memory_reframing"}
    ):
        memories = {item.memory_id: item for item in execution.runtime.memory.store.raw_episodes}
        for target_id in intervention_record.target_ids:
            target = memories.get(target_id)
            if target is None or target.simulation_day > 25 or not target.partner_related:
                raise HarnessError("intervention target is not a pre-shock partner memory")
    shock_confirmed = (
        execution.runtime.shock_validation is not None
        and execution.runtime.shock_validation.event_id == event.event_id
        if record.day == 26
        else False
    )
    previous = execution.evidence[-1].evidence_sha256 if execution.evidence else None
    return HarnessStepEvidence.create(
        cell=execution.cell,
        step_index=record.step_index,
        day=record.day,
        phase=record.phase,
        event_id=record.event_id,
        event_sha256=record.event_sha256,
        event_provenance_source_ids=event.provenance.source_ids,
        held_out_shock_confirmed=shock_confirmed,
        simulation_record_sha256=record.record_sha256,
        simulation_request_sha256=record.request_sha256,
        selected_memories=trace.selected_memories,
        retrieval_record_sha256=context.retrieval_record_sha256,
        memory_checkpoint_sha256=memory_checkpoint.checkpoint_sha256,
        intervention_record_sha256=(
            intervention_record.record_sha256 if intervention_record is not None else None
        ),
        intervention_activated_this_step=record.day == 30,
        intervention_target_ids=(
            intervention_record.target_ids if record.day == 30 and intervention_record else ()
        ),
        pre_action_overlay_sha256=sha256_value(trace.pre_action_overlay),
        active_instruction_sha256=trace.pre_action_overlay.active_instruction_sha256,
        model_input_sha256=sha256_value(trace.model_input),
        action_prompt_sha256=trace.action_prompt_sha256,
        action_cache_key=trace.action_cache_key,
        action_commitment_sha256=record.action.commitment_id,
        public_language_prompt_sha256=trace.public_language_prompt_sha256,
        public_language_cache_key=trace.public_language_cache_key,
        model_ledger_sha256=trace.model_ledger_sha256,
        intervention_ledger_sha256=_intervention_ledger_sha256(execution.runtime),
        resource_total=record.resources.total,
        resource_spent=record.action.cost,
        resource_remaining=record.resources.remaining,
        execution_order=(
            "memory_retrieval",
            "pre_action_overlay",
            "model_input",
            "action_commitment",
            "resource_debit",
            "consequence_application",
            "public_language",
            "memory_commit",
        ),
        action_committed_before_public_language=True,
        previous_evidence_sha256=previous,
    )


def capture_composite_checkpoint(execution: CellExecution) -> CompositeCheckpointBundle:
    state = execution.engine.state
    count = len(execution.evidence)
    if count == 0 or count != state.next_day - 1:
        raise CompositeCheckpointError("checkpoint requires a nonempty aligned evidence chain")
    simulation = SimulationCheckpoint.capture(state=state, checkpoint_sequence=count)
    intervention = execution.runtime.snapshot(state)
    pointer = HarnessCheckpoint.create(
        cell=execution.cell,
        checkpoint_sequence=count,
        next_day=state.next_day,
        simulation_checkpoint_sha256=simulation.checkpoint_sha256,
        simulation_state_sha256=sha256_value(state),
        memory_checkpoint_sha256=intervention.memory.checkpoint_sha256,
        intervention_checkpoint_sha256=intervention.checkpoint_sha256,
        intervention_ledger_sha256=_intervention_ledger_sha256(execution.runtime),
        model_ledger_sha256=execution.model.ledger_sha256,
        evidence_count=count,
        evidence_head_sha256=execution.evidence[-1].evidence_sha256,
    )
    return CompositeCheckpointBundle(
        pointer=pointer,
        simulation=simulation,
        intervention=intervention,
        evidence=tuple(execution.evidence),
    )


def _validate_evidence_chain(
    evidence: tuple[HarnessStepEvidence, ...],
    *,
    cell: HarnessCellIdentity,
) -> None:
    previous: str | None = None
    for index, item in enumerate(evidence):
        if (
            item.cell != cell
            or item.step_index != index
            or item.previous_evidence_sha256 != previous
        ):
            raise CompositeCheckpointError("checkpoint evidence chain is swapped or discontinuous")
        previous = item.evidence_sha256


def restore_composite_checkpoint(
    bundle: CompositeCheckpointBundle,
    *,
    formation: FormationCondition,
    intervention: InterventionCondition,
    loaded: LoadedHarnessConfig,
    project_root: Path,
) -> CellExecution:
    fresh = start_cell(
        formation=formation,
        intervention=intervention,
        loaded=loaded,
        project_root=project_root,
    )
    pointer = bundle.pointer
    if pointer.cell != fresh.cell:
        raise CompositeCheckpointError("composite checkpoint belongs to a different cell")
    _validate_evidence_chain(bundle.evidence, cell=fresh.cell)
    comparisons = (
        pointer.simulation_checkpoint_sha256 == bundle.simulation.checkpoint_sha256,
        pointer.simulation_state_sha256 == sha256_value(bundle.simulation.state),
        pointer.memory_checkpoint_sha256 == bundle.intervention.memory.checkpoint_sha256,
        pointer.intervention_checkpoint_sha256 == bundle.intervention.checkpoint_sha256,
        pointer.intervention_ledger_sha256
        == sha256_value([item.record_sha256 for item in bundle.intervention.records]),
        pointer.evidence_count == len(bundle.evidence),
        pointer.evidence_head_sha256 == bundle.evidence[-1].evidence_sha256,
        pointer.model_ledger_sha256 == bundle.evidence[-1].model_ledger_sha256,
        pointer.next_day == bundle.simulation.state.next_day,
    )
    if not all(comparisons):
        raise CompositeCheckpointError("composite checkpoint component hash mismatch")
    expected = initial_state(fresh.scenario, fresh.model)
    restored_state = bundle.simulation.state
    fixed_fields = (
        "simulation_id",
        "simulation_version",
        "trajectory_id",
        "formation_condition",
        "seed",
        "config_sha256",
        "dataset_sha256",
        "scenario_sha256",
        "model_id",
        "model_revision",
    )
    if any(getattr(expected, name) != getattr(restored_state, name) for name in fixed_fields):
        raise CompositeCheckpointError("simulation checkpoint differs from frozen cell inputs")
    runtime = InterventionRuntime.restore(bundle.intervention, restored_state)
    bridge = HarnessMemoryBridge(runtime)
    prompts = PromptBundle.load(
        project_root / loaded.config.prompt_directory,
        version=loaded.config.prompt_version,
    )
    model = Gate2DeterministicModel(
        scenario=fresh.scenario,
        bridge=bridge,
        prompts=prompts,
        model_config_sha256=fresh.cell.components.model_config_sha256,
        initial_ledger_sha256=pointer.model_ledger_sha256,
    )
    engine = SimulationEngine(fresh.scenario, model, memory=bridge)
    engine.state = restored_state
    return CellExecution(
        cell=fresh.cell,
        scenario=fresh.scenario,
        runtime=runtime,
        bridge=bridge,
        model=model,
        engine=engine,
        evidence=list(bundle.evidence),
    )


def run_cell(
    formation: FormationCondition,
    intervention: InterventionCondition,
    *,
    loaded: LoadedHarnessConfig,
    project_root: Path,
) -> CellExecution:
    execution = start_cell(
        formation=formation,
        intervention=intervention,
        loaded=loaded,
        project_root=project_root,
    )
    execution.run_through(40)
    return execution


def run_cell_resumed(
    formation: FormationCondition,
    intervention: InterventionCondition,
    *,
    loaded: LoadedHarnessConfig,
    project_root: Path,
) -> CellExecution:
    paused = start_cell(
        formation=formation,
        intervention=intervention,
        loaded=loaded,
        project_root=project_root,
    )
    paused.run_through(loaded.config.checkpoint_day)
    checkpoint = capture_composite_checkpoint(paused)
    resumed = restore_composite_checkpoint(
        checkpoint,
        formation=formation,
        intervention=intervention,
        loaded=loaded,
        project_root=project_root,
    )
    resumed.run_through(40)
    return resumed


def _execution_hashes(execution: CellExecution) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(item.record_sha256 for item in execution.engine.state.records),
        tuple(item.evidence_sha256 for item in execution.evidence),
    )


def _validate_pre_intervention_matching(executions: tuple[CellExecution, ...]) -> None:
    by_formation: dict[str, list[CellExecution]] = {}
    for execution in executions:
        by_formation.setdefault(execution.cell.formation_condition, []).append(execution)
    for formation, arms in by_formation.items():
        if len(arms) != 4:
            raise HarnessError(f"formation lacks four intervention arms: {formation}")
        references = tuple(
            (
                item.simulation_record_sha256,
                item.model_input_sha256,
                item.action_prompt_sha256,
                item.action_cache_key,
                item.public_language_prompt_sha256,
                item.public_language_cache_key,
                item.memory_checkpoint_sha256,
                item.model_ledger_sha256,
            )
            for item in arms[0].evidence[:29]
        )
        for arm in arms[1:]:
            comparison = tuple(
                (
                    item.simulation_record_sha256,
                    item.model_input_sha256,
                    item.action_prompt_sha256,
                    item.action_cache_key,
                    item.public_language_prompt_sha256,
                    item.public_language_cache_key,
                    item.memory_checkpoint_sha256,
                    item.model_ledger_sha256,
                )
                for item in arm.evidence[:29]
            )
            if comparison != references:
                raise HarnessError(f"intervention arms diverged before day 30: {formation}")


def _cell_manifest(
    primary: CellExecution,
    resumed: CellExecution,
    replay: CellExecution,
) -> HarnessCellManifest:
    primary_hashes = _execution_hashes(primary)
    if primary_hashes != _execution_hashes(resumed) or primary_hashes != _execution_hashes(replay):
        raise HarnessError("uninterrupted, resumed, and replayed composite hashes differ")
    if len(primary.engine.state.records) != 40 or len(primary.evidence) != 40:
        raise HarnessError("Gate 2 cell did not produce exactly forty committed days")
    record = primary.runtime.records[-1] if primary.runtime.records else None
    shock = primary.runtime.shock_validation
    if record is None or shock is None or not audit_record(record).passed:
        raise HarnessError("Gate 2 cell lacks accepted shock/intervention isolation evidence")
    final_intervention = primary.runtime.snapshot(primary.engine.state)
    return HarnessCellManifest(
        cell=primary.cell,
        trajectory_sha256=SimulationResult.from_state(primary.engine.state).trajectory_sha256,
        evidence_chain_sha256=primary.evidence[-1].evidence_sha256,
        final_simulation_state_sha256=sha256_value(primary.engine.state),
        final_memory_checkpoint_sha256=final_intervention.memory.checkpoint_sha256,
        final_intervention_checkpoint_sha256=final_intervention.checkpoint_sha256,
        final_model_ledger_sha256=primary.model.ledger_sha256,
        record_count=40,
        evidence_count=40,
        shock_event_sha256=shock.event_sha256,
        intervention_record_sha256=record.record_sha256,
        uninterrupted_resumed_match=True,
        replay_matches=True,
        resources_conserved=True,
        action_precedes_language=True,
        interventions_are_isolated=True,
    )


def run_gate2_matrix(
    loaded: LoadedHarnessConfig,
    *,
    project_root: Path,
    failure_injections_passed: tuple[str, ...],
) -> HarnessRunManifest:
    consumed = verify_consumed_artifacts(loaded.config, project_root=project_root)
    primaries: list[CellExecution] = []
    manifests: list[HarnessCellManifest] = []
    for formation in FORMATION_CONDITIONS:
        for intervention in INTERVENTION_CONDITIONS:
            primary = run_cell(
                formation,
                intervention,
                loaded=loaded,
                project_root=project_root,
            )
            resumed = run_cell_resumed(
                formation,
                intervention,
                loaded=loaded,
                project_root=project_root,
            )
            replay = run_cell(
                formation,
                intervention,
                loaded=loaded,
                project_root=project_root,
            )
            manifests.append(_cell_manifest(primary, resumed, replay))
            primaries.append(primary)
    _validate_pre_intervention_matching(tuple(primaries))
    run_id = sha256_value(
        {
            "cells": [item.cell.cell_id for item in manifests],
            "consumed_artifacts": [item.model_dump(mode="json") for item in consumed],
            "engineering_seed": loaded.config.engineering_seed,
            "harness_config_sha256": loaded.config_sha256,
        }
    )
    return HarnessRunManifest.create(
        run_id=run_id,
        evidence_label="deterministic_mock_engineering_evidence",
        scientific_results=False,
        live_calls=0,
        engineering_seed=loaded.config.engineering_seed,
        formation_conditions=FORMATION_CONDITIONS,
        intervention_conditions=INTERVENTION_CONDITIONS,
        consumed_artifacts=consumed,
        cells=tuple(manifests),
        trajectory_count=16,
        record_count=640,
        evidence_count=640,
        failure_injections_passed=failure_injections_passed,
        replay_matches=True,
        interventions_are_isolated=True,
        dataset_separation_protected=True,
        issue_9_default_trajectory_sha256=(
            loaded.config.expected_issue_9_default_trajectory_sha256
        ),
    )
