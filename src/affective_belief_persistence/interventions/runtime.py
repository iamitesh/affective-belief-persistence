"""Day-26 validation and isolated day-30 intervention runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.config import load_yaml
from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.contracts import (
    Memory,
    MemoryInterpretation,
    MemoryModel,
    Sha256,
)
from affective_belief_persistence.memory.integration import (
    DecisionMemoryContext,
    MemoryRuntime,
    MemoryRuntimeCheckpoint,
    PendingMemoryCommit,
)
from affective_belief_persistence.models.contracts import InterventionContext, ModelInput
from affective_belief_persistence.simulation.actions import ActionCommitment
from affective_belief_persistence.simulation.consequences import ConsequenceApplication
from affective_belief_persistence.simulation.state import SimulationState
from affective_belief_persistence.world import ActionOption, Event

from .contracts import (
    InstructionDirective,
    InterventionRecord,
    InterventionSpec,
    LayerSnapshot,
    PreActionOverlay,
    RealityShockValidation,
)


class InterventionError(ValueError):
    """The intervention would violate timing, provenance, or layer isolation."""


@dataclass(frozen=True)
class _PendingActivation:
    """Ephemeral day-30 mutation committed only with the simulation step."""

    staged_memory: MemoryRuntime
    staged_active_instruction_ids: tuple[str, ...]
    record: InterventionRecord


class SimulationCheckpointBinding(MemoryModel):
    """Identity tying the sidecar to one exact Issue #9 simulation state."""

    simulation_id: str = Field(min_length=1)
    trajectory_id: Sha256
    next_day: int = Field(ge=1, le=41)
    simulation_state_sha256: Sha256
    last_step_record_sha256: Sha256 | None

    @classmethod
    def capture(cls, state: SimulationState) -> SimulationCheckpointBinding:
        return cls(
            simulation_id=state.simulation_id,
            trajectory_id=state.trajectory_id,
            next_day=state.next_day,
            simulation_state_sha256=sha256_value(state),
            last_step_record_sha256=(state.records[-1].record_sha256 if state.records else None),
        )


class InterventionCheckpoint(MemoryModel):
    """Hash-protected simulation, memory, and intervention checkpoint bundle."""

    schema_version: Literal["1.0"] = "1.0"
    spec: InterventionSpec
    spec_sha256: Sha256
    instructions: tuple[InstructionDirective, ...]
    active_instruction_ids: tuple[str, ...]
    shock_validation: RealityShockValidation | None
    records: tuple[InterventionRecord, ...]
    memory: MemoryRuntimeCheckpoint
    simulation: SimulationCheckpointBinding
    checkpoint_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"checkpoint_sha256"})

    @model_validator(mode="after")
    def validate_checkpoint(self) -> InterventionCheckpoint:
        if self.spec_sha256 != self.spec.sha256:
            raise ValueError("intervention config hash mismatch")
        instruction_ids = tuple(item.instruction_id for item in self.instructions)
        if len(instruction_ids) != len(set(instruction_ids)):
            raise ValueError("checkpoint instruction IDs must be unique")
        if not set(self.active_instruction_ids).issubset(instruction_ids):
            raise ValueError("active instruction IDs must reference checkpoint instructions")
        if self.checkpoint_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("intervention checkpoint hash mismatch")
        previous: str | None = None
        for record in self.records:
            if record.intervention_config_sha256 != self.spec_sha256:
                raise ValueError("record belongs to another intervention config")
            if record.previous_record_sha256 != previous:
                raise ValueError("intervention records do not form a hash chain")
            previous = record.record_sha256
        if self.simulation.next_day >= 27 and self.shock_validation is None:
            raise ValueError("post-shock checkpoint lacks day-26 validation")
        if self.simulation.next_day >= 31 and len(self.records) != 1:
            raise ValueError("post-intervention checkpoint requires exactly one record")
        return self

    @classmethod
    def capture(
        cls,
        *,
        spec: InterventionSpec,
        instructions: tuple[InstructionDirective, ...],
        active_instruction_ids: tuple[str, ...],
        shock_validation: RealityShockValidation | None,
        records: tuple[InterventionRecord, ...],
        memory: MemoryRuntimeCheckpoint,
        simulation: SimulationCheckpointBinding,
    ) -> InterventionCheckpoint:
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "spec": spec.model_dump(mode="json"),
            "spec_sha256": spec.sha256,
            "instructions": [item.model_dump(mode="json") for item in instructions],
            "active_instruction_ids": active_instruction_ids,
            "shock_validation": (
                shock_validation.model_dump(mode="json") if shock_validation is not None else None
            ),
            "records": [item.model_dump(mode="json") for item in records],
            "memory": memory.model_dump(mode="json"),
            "simulation": simulation.model_dump(mode="json"),
        }
        payload["checkpoint_sha256"] = sha256_value(payload)
        return cls.model_validate(payload)


def load_intervention_spec(path: Path) -> InterventionSpec:
    """Load one duplicate-safe, strict intervention YAML file."""

    if path.is_symlink():
        raise InterventionError("intervention config cannot be a symlink")
    try:
        return InterventionSpec.model_validate(load_yaml(path))
    except (OSError, ValueError) as exc:
        raise InterventionError(f"invalid intervention config {path}: {exc}") from exc


def validate_reality_shock(event: Event) -> RealityShockValidation:
    """Validate the selected protected event without creating or changing it."""

    if event.day != 26 or event.phase != "reality_shock":
        raise InterventionError("reality shock must be the existing day-26 shock event")
    if event.matching_group_id != "heldout-shock-day-26":
        raise InterventionError("reality shock must belong to the held-out matching group")
    if "template-reality-shock" not in event.provenance.source_ids:
        raise InterventionError("day-26 event lacks protected held-out provenance")
    if not event.event_id.startswith("heldout-shock-26-"):
        raise InterventionError("day-26 event ID does not identify the held-out partition")
    authoritative = {
        fact.fact_id
        for fact in event.observable_facts
        if fact.truth and fact.ledger_source == "environment"
    }
    contradictions = tuple(
        evidence
        for evidence in event.relationship_evidence
        if evidence.direction == "contradicts" and set(evidence.fact_ids).issubset(authoritative)
    )
    if not authoritative or not contradictions:
        raise InterventionError("held-out shock lacks authoritative contradictory evidence")
    return RealityShockValidation(
        event_id=event.event_id,
        event_sha256=sha256_value(event),
        day=26,
        phase="reality_shock",
        matching_group_id="heldout-shock-day-26",
        provenance_source_ids=event.provenance.source_ids,
        authoritative_fact_ids=tuple(sorted(authoritative)),
        contradiction_evidence_ids=tuple(sorted(item.evidence_id for item in contradictions)),
    )


def _snapshot(memory: MemoryRuntime, active_instruction_ids: tuple[str, ...]) -> LayerSnapshot:
    raw = memory.store.raw_episodes
    current = {item.memory_id: memory.store.get(item.memory_id) for item in raw}
    facts = [
        {
            "memory_id": item.memory_id,
            "facts": [fact.model_dump(mode="json") for fact in item.observable_facts],
        }
        for item in raw
    ]
    interpretations: list[dict[str, object]] = []
    for item in raw:
        interpretation = current[item.memory_id].interpretation
        interpretations.append(
            {
                "memory_id": item.memory_id,
                "interpretation": (
                    interpretation.model_dump(mode="json") if interpretation is not None else None
                ),
            }
        )
    return LayerSnapshot(
        active_instruction_ids=active_instruction_ids,
        blocked_memory_ids=memory.blocked_memory_ids,
        blocked_condition_tags=memory.blocked_condition_tags,
        memory_ids=tuple(item.memory_id for item in raw),
        memory_storage_sha256=sha256_value([item.model_dump(mode="json") for item in raw]),
        observable_facts_sha256=sha256_value(facts),
        source_event_ids_sha256=sha256_value(
            [(item.memory_id, item.source_event_id) for item in raw]
        ),
        interpretations_sha256=sha256_value(interpretations),
        belief_ledger_sha256=sha256_value(
            [item.model_dump(mode="json") for item in memory.beliefs.versions]
        ),
    )


class InterventionRuntime:
    """MemoryIntegration wrapper activating one treatment before day-30 retrieval."""

    def __init__(
        self,
        spec: InterventionSpec,
        memory: MemoryRuntime,
        *,
        instructions: tuple[InstructionDirective, ...] = (),
    ) -> None:
        instruction_ids = tuple(item.instruction_id for item in instructions)
        if len(instruction_ids) != len(set(instruction_ids)):
            raise InterventionError("active instruction IDs must be unique")
        self.spec = spec
        self.memory = memory
        self.instructions = tuple(sorted(instructions, key=lambda item: item.instruction_id))
        self.active_instruction_ids = tuple(sorted(instruction_ids))
        self.shock_validation: RealityShockValidation | None = None
        self.records: tuple[InterventionRecord, ...] = ()
        self._pending_activation: _PendingActivation | None = None

    def observe_reality_shock(self, event: Event) -> RealityShockValidation:
        validation = validate_reality_shock(event)
        if self.shock_validation is not None and self.shock_validation != validation:
            raise InterventionError("a different day-26 shock was already observed")
        self.shock_validation = validation
        return validation

    def _pre_shock_partner_targets(self, through_day: int) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.memory_id
                for item in self.memory.store.raw_episodes
                if item.partner_related and item.simulation_day <= through_day
            )
        )

    def _reframe_targets(self, through_day: int) -> tuple[str, ...]:
        return tuple(
            memory_id
            for memory_id in self._pre_shock_partner_targets(through_day)
            if self.memory.store.get(memory_id).interpretation is not None
        )

    def _apply_activation(self, *, day: int, append_record: bool) -> InterventionRecord:
        """Mutate the one declared layer after all deterministic prechecks."""

        existing = next(
            (item for item in self.records if item.intervention_id == self.spec.intervention_id),
            None,
        )
        if existing is not None:
            if day != self.spec.activation_day:
                raise InterventionError("an applied intervention cannot be replayed on another day")
            return existing
        if day != self.spec.activation_day:
            raise InterventionError("intervention must activate on frozen day 30")
        if self.shock_validation is None:
            raise InterventionError("day-26 held-out shock must be validated before intervention")

        before = _snapshot(self.memory, self.active_instruction_ids)
        targets: tuple[str, ...] = ()
        reframe_ids: list[str] = []
        no_op_reason: str | None = None
        changed_layers: tuple[str, ...] = ()
        if self.spec.condition == "none":
            no_op_reason = "assigned_no_treatment"
        elif self.spec.condition == "instruction_removal":
            targets = tuple(
                item
                for item in self.spec.target_instruction_ids
                if item in self.active_instruction_ids
            )
            if not targets:
                no_op_reason = "target_instruction_not_active"
            else:
                target_set = set(targets)
                self.active_instruction_ids = tuple(
                    item for item in self.active_instruction_ids if item not in target_set
                )
                changed_layers = ("instructions",)
        elif self.spec.condition == "memory_blocking":
            assert self.spec.block_partner_memories_through_day is not None
            targets = self._pre_shock_partner_targets(self.spec.block_partner_memories_through_day)
            if not targets:
                no_op_reason = "no_eligible_pre_shock_partner_memory"
            else:
                self.memory.set_blocked_memory_ids(targets)
                changed_layers = ("retrieval_policy",)
        elif self.spec.condition == "memory_reframing":
            assert self.spec.reframe_partner_memories_through_day is not None
            targets = self._reframe_targets(self.spec.reframe_partner_memories_through_day)
            if not targets:
                no_op_reason = "no_eligible_pre_shock_partner_memory"
            else:
                assert self.spec.reframe_proposition is not None
                assert self.spec.reframe_policy_version is not None
                current_items = tuple(self.memory.store.get(memory_id) for memory_id in targets)
                for current in current_items:
                    if current.interpretation is None:
                        raise InterventionError("reframe target has no interpretation")
                for current in current_items:
                    prior = current.interpretation
                    assert prior is not None
                    revised = MemoryInterpretation(
                        interpretation_id=(
                            f"{prior.interpretation_id}-reframe-{prior.revision + 1}"
                        ),
                        proposition=self.spec.reframe_proposition,
                        fact_ids=prior.fact_ids,
                        ledger_supported=False,
                        revision=prior.revision + 1,
                    )
                    appended = self.memory.store.reframe(
                        current.memory_id,
                        revised,
                        intervention_id=self.spec.intervention_id,
                        reason=self.spec.reframe_policy_version,
                    )
                    reframe_ids.append(appended.reframe_id)
                changed_layers = ("interpretations",)

        after = _snapshot(self.memory, self.active_instruction_ids)
        record_id = sha256_value(
            {
                "intervention_config_sha256": self.spec.sha256,
                "activation_day": day,
                "shock_event_sha256": self.shock_validation.event_sha256,
            }
        )
        record = InterventionRecord.create(
            record_id=record_id,
            intervention_id=self.spec.intervention_id,
            intervention_condition=self.spec.condition,
            intervention_config_sha256=self.spec.sha256,
            activation_day=day,
            shock_validation=self.shock_validation,
            target_ids=targets,
            changed_layers=changed_layers,
            no_op_reason=no_op_reason,
            before=before,
            after=after,
            appended_reframe_ids=tuple(reframe_ids),
            previous_record_sha256=(self.records[-1].record_sha256 if self.records else None),
            applied_exactly_once=True,
        )
        if append_record:
            self.records = (*self.records, record)
        return record

    def activate(self, *, day: int) -> InterventionRecord:
        """Apply once outside a simulation transaction; retries are idempotent."""

        if self._pending_activation is not None:
            raise InterventionError("cannot directly activate during a pending simulation step")
        return self._apply_activation(day=day, append_record=True)

    def _rollback_pending_activation(self) -> None:
        # The live runtime was never mutated: day 30 runs against a clone until
        # commit. Dropping the clone is therefore a complete rollback.
        self._pending_activation = None

    def abort_pending_step(self) -> None:
        """Explicit failure hook; safe to call repeatedly after a failed day-30 step."""

        self._rollback_pending_activation()

    def pre_action_overlay(self, *, day: int) -> PreActionOverlay:
        """Return prompt-visible instruction and intervention state for a runner."""

        if (
            day >= self.spec.activation_day
            and not self.records
            and self._pending_activation is None
        ):
            raise InterventionError("day-30 activation must precede the pre-action overlay")
        active_ids = (
            self._pending_activation.staged_active_instruction_ids
            if self._pending_activation is not None
            else self.active_instruction_ids
        )
        lookup = {item.instruction_id: item for item in self.instructions}
        active = tuple(lookup[item] for item in active_ids)
        record = (
            self._pending_activation.record
            if self._pending_activation is not None
            else (self.records[-1] if self.records else None)
        )
        return PreActionOverlay(
            day=day,
            active_instructions=active,
            active_instruction_sha256=sha256_value(
                [item.model_dump(mode="json") for item in active]
            ),
            active_intervention_id=(record.intervention_id if record is not None else None),
            intervention_condition=(record.intervention_condition if record is not None else None),
            retrieval_blocked_memory_ids=(
                self._pending_activation.staged_memory.blocked_memory_ids
                if self._pending_activation is not None
                else self.memory.blocked_memory_ids
            ),
            record_sha256=(record.record_sha256 if record is not None else None),
        )

    def get_pre_action_memory(self, memory_id: str) -> Memory:
        """Return an immutable memory view from the state used for this action.

        During the day-30 transaction this reads the isolated staged clone, so
        a composite runner can serialize a reframed interpretation before the
        treatment is committed. The live memory runtime remains unchanged until
        ``commit_after_step`` succeeds.
        """

        source = (
            self._pending_activation.staged_memory
            if self._pending_activation is not None
            else self.memory
        )
        return source.store.get(memory_id)

    def overlay_model_input(self, model_input: ModelInput) -> ModelInput:
        """Bind the active directive text into Issue #12's serialized model input."""

        overlay = self.pre_action_overlay(day=model_input.day)
        directive_text = "\n".join(item.text for item in overlay.active_instructions)
        # Assignment labels and sidecar hashes are deliberately not disclosed
        # to the model. Blocking/reframing act only through memory; instruction
        # removal acts only through this matched instruction-state payload.
        context = InterventionContext(
            intervention_id="pre-action-instruction-state",
            intervention_type="instruction_state",
            parameters={
                "active_instruction_ids": ",".join(
                    item.instruction_id for item in overlay.active_instructions
                ),
                "active_instruction_text": directive_text,
                "active_instruction_sha256": overlay.active_instruction_sha256,
            },
        )
        return model_input.model_copy(
            update={
                "run_id": sha256_value(
                    {
                        "base_run_id": model_input.run_id,
                        "active_instruction_state": [
                            item.model_dump(mode="json") for item in overlay.active_instructions
                        ],
                    }
                ),
                "active_intervention": context,
            }
        )

    def context_for_action(
        self,
        *,
        event: Event,
        goal_ids: tuple[str, ...],
        seed: int,
    ) -> DecisionMemoryContext:
        """Simulation hook: validate/apply before the day's retrieval and action."""

        if event.day == self.spec.activation_day and self._pending_activation is not None:
            # A second request for day 30 means the previous action transaction
            # failed before commit. Restore the exact pre-action sidecars first.
            self._rollback_pending_activation()
        if event.day == 26:
            self.observe_reality_shock(event)
        if event.day == self.spec.activation_day:
            live_memory = self.memory
            instructions_before = self.active_instruction_ids
            staged_memory = MemoryRuntime.restore(live_memory.checkpoint())
            self.memory = staged_memory
            try:
                record = self._apply_activation(day=event.day, append_record=False)
                instructions_after = self.active_instruction_ids
            finally:
                self.memory = live_memory
                self.active_instruction_ids = instructions_before
            self._pending_activation = _PendingActivation(
                staged_memory=staged_memory,
                staged_active_instruction_ids=instructions_after,
                record=record,
            )
        try:
            target_memory = (
                self._pending_activation.staged_memory
                if self._pending_activation is not None
                else self.memory
            )
            return target_memory.context_for_action(event=event, goal_ids=goal_ids, seed=seed)
        except Exception:
            self._rollback_pending_activation()
            raise

    def prepare_pre_action(
        self,
        *,
        event: Event,
        goal_ids: tuple[str, ...],
        seed: int,
        model_input: ModelInput,
    ) -> tuple[DecisionMemoryContext, ModelInput, PreActionOverlay]:
        """Composite hook for richer runners that need memory plus instruction state."""

        if model_input.day != event.day or model_input.event_id != event.event_id:
            raise InterventionError("model input does not describe the supplied event")
        memory_context = self.context_for_action(event=event, goal_ids=goal_ids, seed=seed)
        enriched = self.overlay_model_input(model_input)
        return memory_context, enriched, self.pre_action_overlay(day=event.day)

    def stage_after_consequence(
        self,
        *,
        event: Event,
        action: ActionOption,
        commitment: ActionCommitment,
        consequence: ConsequenceApplication,
        decision_context: DecisionMemoryContext,
    ) -> PendingMemoryCommit:
        try:
            target_memory = (
                self._pending_activation.staged_memory
                if self._pending_activation is not None
                else self.memory
            )
            return target_memory.stage_after_consequence(
                event=event,
                action=action,
                commitment=commitment,
                consequence=consequence,
                decision_context=decision_context,
            )
        except Exception:
            self._rollback_pending_activation()
            raise

    def commit_after_step(self, pending: PendingMemoryCommit, *, source_record_sha256: str) -> None:
        target_memory = (
            self._pending_activation.staged_memory
            if self._pending_activation is not None
            else self.memory
        )
        try:
            target_memory.commit_after_step(
                pending,
                source_record_sha256=source_record_sha256,
            )
        except Exception:
            self._rollback_pending_activation()
            raise
        if self._pending_activation is not None:
            staged = self._pending_activation
            self.memory = staged.staged_memory
            self.active_instruction_ids = staged.staged_active_instruction_ids
            record = staged.record
            self.records = (*self.records, record)
            self._pending_activation = None

    def checkpoint(self) -> MemoryRuntimeCheckpoint:
        """MemoryIntegration-compatible checkpoint accessor."""

        # A failed action/language stage has no commit callback. Checkpointing
        # is a durability boundary, so discard its ephemeral treatment first.
        self._rollback_pending_activation()
        return self.memory.checkpoint()

    def snapshot(self, simulation_state: SimulationState) -> InterventionCheckpoint:
        """Capture exact simulation, memory, instruction, and treatment identity."""

        self._rollback_pending_activation()
        return InterventionCheckpoint.capture(
            spec=self.spec,
            instructions=self.instructions,
            active_instruction_ids=self.active_instruction_ids,
            shock_validation=self.shock_validation,
            records=self.records,
            memory=self.memory.checkpoint(),
            simulation=SimulationCheckpointBinding.capture(simulation_state),
        )

    @classmethod
    def restore(
        cls,
        checkpoint: InterventionCheckpoint,
        simulation_state: SimulationState,
    ) -> InterventionRuntime:
        if SimulationCheckpointBinding.capture(simulation_state) != checkpoint.simulation:
            raise InterventionError(
                "intervention checkpoint belongs to a different simulation state"
            )
        runtime = cls(
            checkpoint.spec,
            MemoryRuntime.restore(checkpoint.memory),
            instructions=checkpoint.instructions,
        )
        runtime.active_instruction_ids = checkpoint.active_instruction_ids
        runtime.shock_validation = checkpoint.shock_validation
        runtime.records = checkpoint.records
        runtime._pending_activation = None
        return runtime

    def fresh(self) -> InterventionRuntime:
        return InterventionRuntime(
            self.spec,
            self.memory.fresh(),
            instructions=self.instructions,
        )
