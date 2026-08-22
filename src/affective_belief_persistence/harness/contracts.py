"""Strict Gate 2 evidence contracts with no repository-schema import cycle."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")]
FormationCondition = Literal[
    "neutral_connection",
    "romantic_prompt",
    "shared_memory",
    "memory_plus_investment",
]
InterventionCondition = Literal[
    "none",
    "instruction_removal",
    "memory_blocking",
    "memory_reframing",
]
SimulationPhase = Literal["baseline", "formation", "reality_shock", "adaptation"]

FORMATION_CONDITIONS: tuple[FormationCondition, ...] = (
    "neutral_connection",
    "romantic_prompt",
    "shared_memory",
    "memory_plus_investment",
)
INTERVENTION_CONDITIONS: tuple[InterventionCondition, ...] = (
    "none",
    "instruction_removal",
    "memory_blocking",
    "memory_reframing",
)


class HarnessModel(BaseModel):
    """Immutable fail-closed boundary for Gate 2 artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CellComponentHashes(HarnessModel):
    """Every component that can change a factorial cell's behavior."""

    harness_config_sha256: Sha256
    dataset_sha256: Sha256
    dataset_manifest_sha256: Sha256
    world_input_sha256: Sha256
    scenario_sha256: Sha256
    simulation_config_sha256: Sha256
    memory_config_sha256: Sha256
    intervention_config_sha256: Sha256
    model_config_sha256: Sha256
    prompt_bundle_sha256: Sha256
    simulation_artifact_sha256: Sha256
    memory_artifact_sha256: Sha256
    intervention_artifact_sha256: Sha256
    model_runner_artifact_sha256: Sha256


class HarnessCellIdentity(HarnessModel):
    """Collision-resistant identity for one formation/intervention assignment."""

    formation_condition: FormationCondition
    intervention_condition: InterventionCondition
    engineering_seed: int = Field(ge=0, le=2**63 - 1)
    components: CellComponentHashes
    cell_id: Sha256

    def identity_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"cell_id"})

    @model_validator(mode="after")
    def validate_cell_id(self) -> HarnessCellIdentity:
        if self.cell_id != sha256_value(self.identity_payload()):
            raise ValueError("harness cell ID does not bind the complete assignment")
        return self

    @classmethod
    def create(cls, **values: object) -> HarnessCellIdentity:
        payload = {**values, "cell_id": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["cell_id"] = sha256_value(provisional.identity_payload())
        return cls.model_validate(payload)


class SelectedMemoryEvidence(HarnessModel):
    """Safe prompt-visible content for one selected synthetic episode."""

    memory_id: Identifier
    summary: str = Field(min_length=1)
    observable_facts: tuple[str, ...]
    active_interpretation: str | None = None
    active_interpretation_id: Identifier | None = None
    active_interpretation_revision: int | None = Field(default=None, ge=1)
    source_ids: tuple[Identifier, ...] = Field(min_length=1)
    content_sha256: Sha256

    def content_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"content_sha256"})

    @model_validator(mode="after")
    def validate_content(self) -> SelectedMemoryEvidence:
        interpretation_fields = (
            self.active_interpretation,
            self.active_interpretation_id,
            self.active_interpretation_revision,
        )
        if any(value is None for value in interpretation_fields) and any(
            value is not None for value in interpretation_fields
        ):
            raise ValueError("active interpretation fields must be all present or all absent")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("selected memory source IDs must be unique")
        if self.content_sha256 != sha256_value(self.content_payload()):
            raise ValueError("selected memory content hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> SelectedMemoryEvidence:
        payload = {**values, "content_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["content_sha256"] = sha256_value(provisional.content_payload())
        return cls.model_validate(payload)


class HarnessStepEvidence(HarnessModel):
    """Hash-chained sidecar proving one composite action-first day."""

    schema_version: Literal["1.0"] = "1.0"
    cell: HarnessCellIdentity
    step_index: int = Field(ge=0, le=39)
    day: int = Field(ge=1, le=40)
    phase: SimulationPhase
    event_id: Identifier
    event_sha256: Sha256
    event_provenance_source_ids: tuple[Identifier, ...]
    held_out_shock_confirmed: bool
    simulation_record_sha256: Sha256
    simulation_request_sha256: Sha256
    selected_memories: tuple[SelectedMemoryEvidence, ...]
    retrieval_record_sha256: Sha256 | None
    memory_checkpoint_sha256: Sha256
    intervention_record_sha256: Sha256 | None
    intervention_activated_this_step: bool
    intervention_target_ids: tuple[Identifier, ...]
    pre_action_overlay_sha256: Sha256
    active_instruction_sha256: Sha256
    model_input_sha256: Sha256
    action_prompt_sha256: Sha256
    action_cache_key: Sha256
    action_commitment_sha256: Sha256
    public_language_prompt_sha256: Sha256
    public_language_cache_key: Sha256
    model_ledger_sha256: Sha256
    intervention_ledger_sha256: Sha256
    resource_total: Literal[10]
    resource_spent: int = Field(ge=0, le=10)
    resource_remaining: int = Field(ge=0, le=10)
    execution_order: tuple[
        Literal["memory_retrieval"],
        Literal["pre_action_overlay"],
        Literal["model_input"],
        Literal["action_commitment"],
        Literal["resource_debit"],
        Literal["consequence_application"],
        Literal["public_language"],
        Literal["memory_commit"],
    ]
    action_committed_before_public_language: Literal[True]
    previous_evidence_sha256: Sha256 | None = None
    evidence_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"evidence_sha256"})

    @model_validator(mode="after")
    def validate_step(self) -> HarnessStepEvidence:
        expected_phase: SimulationPhase
        if self.day <= 5:
            expected_phase = "baseline"
        elif self.day <= 25:
            expected_phase = "formation"
        elif self.day == 26:
            expected_phase = "reality_shock"
        else:
            expected_phase = "adaptation"
        if self.step_index != self.day - 1 or self.phase != expected_phase:
            raise ValueError("Gate 2 day, index, and phase do not agree")
        if self.held_out_shock_confirmed != (self.day == 26):
            raise ValueError("held-out shock confirmation must occur exactly on day 26")
        if self.day == 26 and "template-reality-shock" not in self.event_provenance_source_ids:
            raise ValueError("day 26 evidence lacks protected held-out provenance")
        if self.intervention_activated_this_step != (self.day == 30):
            raise ValueError("intervention activation must be recorded exactly on day 30")
        if (self.intervention_record_sha256 is not None) != (self.day >= 30):
            raise ValueError("post-day-30 evidence must bind the intervention record")
        if self.intervention_target_ids and self.day != 30:
            raise ValueError("intervention targets are recorded only on the activation step")
        selected_ids = tuple(item.memory_id for item in self.selected_memories)
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("selected memory evidence must be unique")
        if self.resource_spent + self.resource_remaining != self.resource_total:
            raise ValueError("Gate 2 resource evidence is not conserved")
        expected_order = (
            "memory_retrieval",
            "pre_action_overlay",
            "model_input",
            "action_commitment",
            "resource_debit",
            "consequence_application",
            "public_language",
            "memory_commit",
        )
        if self.execution_order != expected_order:
            raise ValueError("Gate 2 action-first execution order changed")
        if self.evidence_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("Gate 2 step evidence hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> HarnessStepEvidence:
        payload = {**values, "evidence_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["evidence_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


class HarnessCheckpoint(HarnessModel):
    """Composite pointer binding every independently restorable ledger."""

    schema_version: Literal["1.0"] = "1.0"
    cell: HarnessCellIdentity
    checkpoint_sequence: int = Field(ge=1, le=40)
    next_day: int = Field(ge=2, le=41)
    simulation_checkpoint_sha256: Sha256
    simulation_state_sha256: Sha256
    memory_checkpoint_sha256: Sha256
    intervention_checkpoint_sha256: Sha256
    intervention_ledger_sha256: Sha256
    model_ledger_sha256: Sha256
    evidence_count: int = Field(ge=1, le=40)
    evidence_head_sha256: Sha256
    checkpoint_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"checkpoint_sha256"})

    @model_validator(mode="after")
    def validate_checkpoint(self) -> HarnessCheckpoint:
        if self.evidence_count != self.next_day - 1:
            raise ValueError("composite checkpoint evidence does not end before next_day")
        if self.checkpoint_sequence != self.evidence_count:
            raise ValueError("composite checkpoint sequence must equal committed steps")
        if self.checkpoint_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("composite checkpoint hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> HarnessCheckpoint:
        payload = {**values, "checkpoint_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["checkpoint_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


class HarnessCellManifest(HarnessModel):
    cell: HarnessCellIdentity
    trajectory_sha256: Sha256
    evidence_chain_sha256: Sha256
    final_simulation_state_sha256: Sha256
    final_memory_checkpoint_sha256: Sha256
    final_intervention_checkpoint_sha256: Sha256
    final_model_ledger_sha256: Sha256
    record_count: Literal[40]
    evidence_count: Literal[40]
    shock_event_sha256: Sha256
    intervention_record_sha256: Sha256
    uninterrupted_resumed_match: Literal[True]
    replay_matches: Literal[True]
    resources_conserved: Literal[True]
    action_precedes_language: Literal[True]
    interventions_are_isolated: Literal[True]


class ConsumedArtifact(HarnessModel):
    artifact_id: Literal[
        "issue-9-simulation-harness",
        "issue-10-memory-subsystem",
        "issue-11-intervention-engine",
        "issue-12-model-runner",
    ]
    path: str = Field(min_length=1)
    sha256: Sha256


class HarnessRunManifest(HarnessModel):
    """Exact one-seed 4x4 Gate 2 engineering manifest."""

    schema_version: Literal["1.0"] = "1.0"
    run_id: Sha256
    task_id: Literal["gate-2-harness"] = "gate-2-harness"
    gate_id: Literal["gate-2"] = "gate-2"
    artifact_id: Literal["gate-2-evidence"] = "gate-2-evidence"
    status: Literal["passed"] = "passed"
    evidence_label: Literal["deterministic_mock_engineering_evidence"]
    scientific_results: Literal[False]
    live_calls: Literal[0]
    engineering_seed: int = Field(ge=0, le=2**63 - 1)
    formation_conditions: tuple[FormationCondition, ...]
    intervention_conditions: tuple[InterventionCondition, ...]
    consumed_artifacts: tuple[ConsumedArtifact, ...]
    cells: tuple[HarnessCellManifest, ...]
    trajectory_count: Literal[16]
    record_count: Literal[640]
    evidence_count: Literal[640]
    failure_injections_passed: tuple[Identifier, ...]
    replay_matches: Literal[True]
    interventions_are_isolated: Literal[True]
    dataset_separation_protected: Literal[True]
    issue_9_default_trajectory_sha256: Sha256
    manifest_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"manifest_sha256"})

    @model_validator(mode="after")
    def validate_matrix(self) -> HarnessRunManifest:
        if self.formation_conditions != FORMATION_CONDITIONS:
            raise ValueError("Gate 2 must contain exactly the four frozen formations")
        if self.intervention_conditions != INTERVENTION_CONDITIONS:
            raise ValueError("Gate 2 must contain exactly the four frozen interventions")
        artifact_ids = tuple(item.artifact_id for item in self.consumed_artifacts)
        expected_artifacts = (
            "issue-9-simulation-harness",
            "issue-10-memory-subsystem",
            "issue-11-intervention-engine",
            "issue-12-model-runner",
        )
        if artifact_ids != expected_artifacts:
            raise ValueError("Gate 2 must consume accepted Issues 9, 10, 11, and 12")
        assignments = {
            (item.cell.formation_condition, item.cell.intervention_condition) for item in self.cells
        }
        expected_assignments = {
            (formation, intervention)
            for formation in FORMATION_CONDITIONS
            for intervention in INTERVENTION_CONDITIONS
        }
        if len(self.cells) != 16 or assignments != expected_assignments:
            raise ValueError("Gate 2 manifest does not contain the exact 4x4 matrix")
        if len({item.cell.cell_id for item in self.cells}) != 16:
            raise ValueError("Gate 2 cell IDs must be collision-free")
        if any(item.cell.engineering_seed != self.engineering_seed for item in self.cells):
            raise ValueError("every Gate 2 cell must use the one engineering seed")
        if self.manifest_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("Gate 2 manifest hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> HarnessRunManifest:
        payload = {**values, "manifest_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["manifest_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


HARNESS_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "harness-step-evidence.schema.json": HarnessStepEvidence,
    "harness-checkpoint.schema.json": HarnessCheckpoint,
    "harness-run-manifest.schema.json": HarnessRunManifest,
}
