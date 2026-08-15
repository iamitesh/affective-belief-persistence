"""Deterministic action-first simulation engine with checkpoint/resume."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import ValidationError

from affective_belief_persistence.config import find_project_root
from affective_belief_persistence.determinism import (
    canonical_json,
    derive_seed,
    sha256_file,
    sha256_value,
)
from affective_belief_persistence.schemas import ActionOption as RequestActionOption
from affective_belief_persistence.schemas import DecisionRequest, ModelDecision
from affective_belief_persistence.simulation.actions import commit_action
from affective_belief_persistence.simulation.clock import (
    COMPLETED_DAY,
    SimulationClock,
    phase_for_day,
)
from affective_belief_persistence.simulation.consequences import (
    apply_consequence,
    update_goal_progress,
)
from affective_belief_persistence.simulation.model import (
    DeterministicTwoStageMockModel,
    SimulationModel,
)
from affective_belief_persistence.simulation.resources import DailyResourceLedger
from affective_belief_persistence.simulation.scenario_loader import LoadedScenario, load_scenario
from affective_belief_persistence.simulation.state import (
    ReplayReport,
    SimulationArtifact,
    SimulationCheckpoint,
    SimulationResult,
    SimulationRunManifest,
    SimulationState,
    SimulationStepRecord,
)


class SimulationError(RuntimeError):
    """The simulator cannot continue without violating a frozen invariant."""


class CheckpointError(SimulationError):
    """A checkpoint is absent, corrupt, or belongs to different frozen inputs."""


def _trajectory_id(scenario: LoadedScenario, model: SimulationModel) -> str:
    return sha256_value(
        {
            "config_sha256": scenario.config_sha256,
            "dataset_sha256": scenario.manifest.dataset_sha256,
            "formation_condition": scenario.config.formation_condition,
            "model_id": model.model_id,
            "model_revision": model.revision,
            "scenario_sha256": scenario.scenario_sha256,
            "seed": scenario.config.seed,
        }
    )


def initial_state(scenario: LoadedScenario, model: SimulationModel) -> SimulationState:
    """Create the canonical empty state for a scenario/adapter pair."""

    return SimulationState(
        simulation_id=scenario.config.simulation_id,
        simulation_version=scenario.config.version,
        trajectory_id=_trajectory_id(scenario, model),
        formation_condition=scenario.config.formation_condition,
        seed=scenario.config.seed,
        config_sha256=scenario.config_sha256,
        dataset_sha256=scenario.manifest.dataset_sha256,
        scenario_sha256=scenario.scenario_sha256,
        model_id=model.model_id,
        model_revision=model.revision,
        next_day=1,
        records=(),
        goal_progress={},
        completed=False,
    )


def load_checkpoint(path: Path) -> SimulationCheckpoint:
    """Load and hash-validate a simulation checkpoint."""

    if not path.is_file() or path.is_symlink():
        raise CheckpointError(f"checkpoint must be an existing regular file: {path}")
    try:
        return SimulationCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise CheckpointError(f"invalid simulation checkpoint {path}: {exc}") from exc


class SimulationEngine:
    """Execute one immutable daily action per event in deterministic simulated time."""

    def __init__(
        self,
        scenario: LoadedScenario,
        model: SimulationModel,
        *,
        checkpoint_path: Path | None = None,
        resume: bool = False,
    ) -> None:
        if model.model_id != scenario.model_settings.model_id:
            raise SimulationError("adapter model_id does not match the frozen model config")
        if model.revision != scenario.model_settings.revision:
            raise SimulationError("adapter revision does not match the frozen model config")
        self.scenario = scenario
        self.model = model
        self.checkpoint_path = checkpoint_path.resolve() if checkpoint_path is not None else None
        self.checkpoint_sequence = 0
        expected = initial_state(scenario, model)
        if resume:
            if self.checkpoint_path is None:
                raise CheckpointError("resume requires checkpoint_path")
            checkpoint = load_checkpoint(self.checkpoint_path)
            self._validate_resumed_state(checkpoint.state, expected)
            self.state = checkpoint.state
            self.checkpoint_sequence = checkpoint.checkpoint_sequence
        else:
            self.state = expected

    def _validate_resumed_state(self, restored: SimulationState, expected: SimulationState) -> None:
        comparisons = {
            "simulation_id": (restored.simulation_id, expected.simulation_id),
            "simulation_version": (restored.simulation_version, expected.simulation_version),
            "trajectory_id": (restored.trajectory_id, expected.trajectory_id),
            "config_sha256": (restored.config_sha256, expected.config_sha256),
            "dataset_sha256": (restored.dataset_sha256, expected.dataset_sha256),
            "scenario_sha256": (restored.scenario_sha256, expected.scenario_sha256),
            "model_id": (restored.model_id, expected.model_id),
            "model_revision": (restored.model_revision, expected.model_revision),
            "formation_condition": (
                restored.formation_condition,
                expected.formation_condition,
            ),
            "seed": (restored.seed, expected.seed),
        }
        differences = [name for name, (actual, wanted) in comparisons.items() if actual != wanted]
        if differences:
            raise CheckpointError(
                "checkpoint belongs to different frozen inputs: " + ", ".join(differences)
            )
        for record, event in zip(restored.records, self.scenario.events, strict=False):
            if record.event_id != event.event_id or record.day != event.day:
                raise CheckpointError("checkpoint record order differs from the frozen scenario")

    def _write_checkpoint(self) -> SimulationCheckpoint | None:
        if self.checkpoint_path is None:
            return None
        path = self.checkpoint_path
        if path.exists() and path.is_symlink():
            raise CheckpointError(f"checkpoint path cannot be a symlink: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise CheckpointError(f"checkpoint parent cannot be a symlink: {path.parent}")
        self.checkpoint_sequence += 1
        checkpoint = SimulationCheckpoint.capture(
            state=self.state, checkpoint_sequence=self.checkpoint_sequence
        )
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_text(canonical_json(checkpoint) + "\n", encoding="utf-8", newline="\n")
            os.replace(temporary, path)
        except OSError as exc:
            raise CheckpointError(f"could not atomically save checkpoint {path}: {exc}") from exc
        return checkpoint

    def step(self) -> SimulationStepRecord:
        """Run the next unfinished day with a two-phase action/language commit."""

        clock = SimulationClock(next_day=self.state.next_day)
        if clock.complete:
            raise SimulationError("simulation is already complete")
        event = self.scenario.events[clock.next_day - 1]
        if event.day != clock.next_day or event.phase != phase_for_day(clock.next_day):
            raise SimulationError("scenario event does not match the simulated clock")
        actions_by_id = {action.action_id: action for action in self.scenario.actions}
        consequences_by_id = {
            consequence.consequence_id: consequence for consequence in self.scenario.consequences
        }
        available_actions: list[RequestActionOption] = []
        for action_id in event.available_action_ids:
            try:
                action = actions_by_id[action_id]
            except KeyError as exc:
                raise SimulationError(f"event references unknown action: {action_id}") from exc
            if action.cost > self.scenario.budget.daily_total:
                raise SimulationError(f"action exceeds daily budget: {action_id}")
            available_actions.append(
                RequestActionOption(
                    action_id=action.action_id,
                    description=action.description,
                    cost=action.cost,
                )
            )
        request_id = sha256_value(
            {
                "day": event.day,
                "matching_group_id": event.matching_group_id,
                "prompt_version": self.scenario.config.prompt_version,
                "schema_version": self.scenario.config.decision_schema_version,
            }
        )
        request = DecisionRequest(
            schema_version=self.scenario.config.decision_schema_version,
            request_id=request_id,
            event_id=event.event_id,
            day=event.day,
            facts=[fact.proposition for fact in event.observable_facts if fact.truth],
            action_points=self.scenario.budget.daily_total,
            available_actions=available_actions,
            retrieved_memory_ids=[],
            beliefs={},
        )
        action_selection_seed = derive_seed(
            self.scenario.config.seed,
            "action-selection",
            event.matching_group_id,
            f"day-{event.day}",
        ) % (2**63)
        public_language_seed = derive_seed(
            self.scenario.config.seed,
            "public-language",
            event.matching_group_id,
            f"day-{event.day}",
        ) % (2**63)
        selection = self.model.select_action(request, seed=action_selection_seed)

        # Phase 1: validate and commit structured behavior. No public language is
        # attached to mutable simulation state during these three operations.
        commitment = commit_action(event, actions_by_id, selection)
        ledger = DailyResourceLedger(
            day=event.day,
            budget_id=self.scenario.budget.resource_budget_id,
            total=self.scenario.budget.daily_total,
            remaining=self.scenario.budget.daily_total,
        ).debit(
            event_id=event.event_id,
            decision_id=selection.decision_id,
            action_id=commitment.action_id,
            amount=commitment.cost,
        )
        consequence = apply_consequence(commitment, consequences_by_id)
        goal_progress = update_goal_progress(self.state.goal_progress, consequence)

        # Phase 2: only after the action debit and consequence succeed is the
        # adapter's public response released into the append-only step record.
        public_response = self.model.generate_public_language(
            request,
            selection,
            action_commitment_sha256=commitment.commitment_id,
            seed=public_language_seed,
        )
        decision = ModelDecision(
            schema_version=self.scenario.config.decision_schema_version,
            decision_id=selection.decision_id,
            chosen_action=selection.chosen_action,
            resources_spent=selection.resources_spent,
            retrieved_memory_ids=list(selection.retrieved_memory_ids),
            belief_updates=list(selection.belief_updates),
            public_response=public_response,
        )
        record = SimulationStepRecord.create(
            step_index=event.day - 1,
            day=event.day,
            phase=phase_for_day(event.day),
            trajectory_id=self.state.trajectory_id,
            event_id=event.event_id,
            matching_group_id=event.matching_group_id,
            event_sha256=sha256_value(event),
            config_sha256=self.scenario.config_sha256,
            dataset_sha256=self.scenario.manifest.dataset_sha256,
            scenario_sha256=self.scenario.scenario_sha256,
            request_id=request.request_id,
            request_sha256=sha256_value(request),
            root_seed=self.scenario.config.seed,
            action_selection_seed=action_selection_seed,
            public_language_seed=public_language_seed,
            action_menu_sha256=sha256_value(
                [
                    {"action_id": action.action_id, "cost": action.cost}
                    for action in available_actions
                ]
            ),
            available_action_ids=tuple(event.available_action_ids),
            available_action_costs={action.action_id: action.cost for action in available_actions},
            foregone_action_ids=tuple(
                action_id
                for action_id in event.available_action_ids
                if action_id != selection.chosen_action
            ),
            chosen_action_partner_directed=actions_by_id[selection.chosen_action].partner_directed,
            memory_candidate_ids=tuple(item.memory_id for item in event.memory_candidates),
            previous_record_sha256=(
                self.state.records[-1].record_sha256 if self.state.records else None
            ),
            intervention_eligible=event.day >= 30,
            applied_intervention_ids=(),
            decision=decision,
            action=commitment,
            resources=ledger,
            consequence=consequence,
            model_id=self.model.model_id,
            model_revision=self.model.revision,
        )
        next_day = event.day + 1
        self.state = SimulationState(
            **self.state.model_dump(exclude={"next_day", "records", "goal_progress", "completed"}),
            next_day=next_day,
            records=(*self.state.records, record),
            goal_progress=goal_progress,
            completed=next_day == COMPLETED_DAY,
        )
        cadence_due = len(self.state.records) % self.scenario.config.checkpoint_cadence_steps == 0
        if self.state.completed or cadence_due:
            self._write_checkpoint()
        return record

    def run(self, *, max_steps: int | None = None) -> SimulationResult:
        """Run to completion or pause after ``max_steps`` newly executed days."""

        if max_steps is not None and max_steps < 0:
            raise SimulationError("max_steps cannot be negative")
        executed = 0
        while not self.state.completed and (max_steps is None or executed < max_steps):
            self.step()
            executed += 1
        if self.checkpoint_path is not None and not self.state.completed:
            # A caller-requested pause is itself a recovery boundary, even when it
            # falls between the configured periodic checkpoints.
            self._write_checkpoint()
        return SimulationResult.from_state(self.state)


def run_simulation(
    config_path: Path,
    *,
    project_root: Path | None = None,
    model: SimulationModel | None = None,
    checkpoint_path: Path | None = None,
    resume: bool = False,
    max_steps: int | None = None,
) -> SimulationResult:
    """Load frozen inputs and execute (or resume) one forty-day trajectory."""

    root = (project_root or find_project_root(config_path)).resolve()
    scenario = load_scenario(config_path, project_root=root)
    adapter = model or DeterministicTwoStageMockModel(scenario.model_settings)
    engine = SimulationEngine(
        scenario,
        adapter,
        checkpoint_path=checkpoint_path,
        resume=resume,
    )
    return engine.run(max_steps=max_steps)


def _write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _simulation_artifact(
    path: Path, output: Path, *, logical_name: str, media_type: str
) -> SimulationArtifact:
    if path.is_symlink() or not path.resolve().is_relative_to(output.resolve()):
        raise SimulationError(f"simulation artifact escapes its output directory: {path}")
    return SimulationArtifact(
        logical_name=logical_name,
        path=path.relative_to(output).as_posix(),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        media_type=media_type,
    )


def run_and_write_simulation(
    config_path: Path,
    output_dir: Path,
    *,
    project_root: Path | None = None,
    model: SimulationModel | None = None,
    resume: bool = False,
    max_steps: int | None = None,
) -> SimulationRunManifest:
    """Execute, deterministically replay, and atomically write a simulation run."""

    if output_dir.is_symlink():
        raise SimulationError(f"output directory cannot be a symlink: {output_dir}")
    output = output_dir.resolve()
    if not resume and output.exists() and any(output.iterdir()):
        raise SimulationError(f"output directory must be empty: {output_dir}")
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / "checkpoints/latest.json"
    if resume and not checkpoint_path.is_file():
        raise CheckpointError(f"resume checkpoint does not exist: {checkpoint_path}")

    root = (project_root or find_project_root(config_path)).resolve()
    scenario = load_scenario(config_path, project_root=root)
    adapter = model or DeterministicTwoStageMockModel(scenario.model_settings)
    engine = SimulationEngine(
        scenario,
        adapter,
        checkpoint_path=checkpoint_path,
        resume=resume,
    )
    result = engine.run(max_steps=max_steps)

    records_path = output / "step-records.jsonl"
    _write_atomic(
        records_path,
        "".join(canonical_json(record) + "\n" for record in result.state.records),
    )

    replay_adapter: SimulationModel
    if model is None:
        replay_adapter = DeterministicTwoStageMockModel(scenario.model_settings)
    else:
        replay_adapter = model
    replay_result = SimulationEngine(scenario, replay_adapter).run(
        max_steps=len(result.state.records)
    )
    step_hashes_match = [item.record_sha256 for item in result.state.records] == [
        item.record_sha256 for item in replay_result.state.records
    ]
    resources_conserved = all(
        record.resources.total == 10
        and record.resources.remaining
        == record.resources.total - sum(debit.amount for debit in record.resources.debits)
        and record.consequence.resource_delta == -record.action.cost
        for record in result.state.records
    )
    action_first = all(
        record.action_committed_before_public_language
        and record.execution_order
        == (
            "action_commitment",
            "resource_debit",
            "consequence_application",
            "public_language",
        )
        for record in result.state.records
    )
    if (
        not step_hashes_match
        or result.trajectory_sha256 != replay_result.trajectory_sha256
        or not resources_conserved
        or not action_first
    ):
        raise SimulationError("deterministic replay or simulation invariant check failed")
    replay_report = ReplayReport(
        trajectory_id=result.state.trajectory_id,
        original_trajectory_sha256=result.trajectory_sha256,
        replay_trajectory_sha256=replay_result.trajectory_sha256,
        record_count=len(result.state.records),
        step_hashes_match=True,
        resources_are_conserved=True,
        action_precedes_public_language=True,
    )
    replay_path = output / "replay-report.json"
    _write_atomic(replay_path, canonical_json(replay_report) + "\n")

    artifacts = (
        _simulation_artifact(
            records_path,
            output,
            logical_name="simulation_step_records",
            media_type="application/x-ndjson",
        ),
        _simulation_artifact(
            checkpoint_path,
            output,
            logical_name="simulation_checkpoint",
            media_type="application/json",
        ),
        _simulation_artifact(
            replay_path,
            output,
            logical_name="simulation_replay_report",
            media_type="application/json",
        ),
    )
    manifest = SimulationRunManifest(
        run_id=result.state.trajectory_id,
        status="completed" if result.state.completed else "paused",
        simulation_id=result.state.simulation_id,
        simulation_version=result.state.simulation_version,
        formation_condition=result.state.formation_condition,
        seed=result.state.seed,
        model_id=result.state.model_id,
        model_revision=result.state.model_revision,
        config_sha256=result.state.config_sha256,
        dataset_sha256=result.state.dataset_sha256,
        dataset_manifest_sha256=scenario.manifest_sha256,
        scenario_sha256=result.state.scenario_sha256,
        world_artifact_sha256=scenario.world_artifact_sha256,
        world_input_sha256=scenario.world_input_sha256,
        model_config_sha256=scenario.model_config_sha256,
        trajectory_sha256=result.trajectory_sha256,
        record_count=len(result.state.records),
        next_day=result.state.next_day,
        artifacts=artifacts,
    )
    manifest_path = output / "run-manifest.json"
    _write_atomic(manifest_path, canonical_json(manifest) + "\n")
    return manifest
