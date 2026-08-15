"""Immutable simulation records, state snapshots, and checkpoint contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.schemas import FormationCondition, ModelDecision
from affective_belief_persistence.simulation.actions import ActionCommitment
from affective_belief_persistence.simulation.clock import (
    COMPLETED_DAY,
    SimulationPhase,
    phase_for_day,
)
from affective_belief_persistence.simulation.consequences import ConsequenceApplication
from affective_belief_persistence.simulation.resources import DailyResourceLedger

Sha256Pattern = r"^[0-9a-f]{64}$"


class SimulationStepRecord(BaseModel):
    """Append-only evidence for one action-first simulated day."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    step_index: int = Field(ge=0, le=39)
    day: int = Field(ge=1, le=40)
    phase: SimulationPhase
    trajectory_id: str = Field(pattern=Sha256Pattern)
    event_id: str = Field(min_length=1)
    matching_group_id: str = Field(min_length=1)
    event_sha256: str = Field(pattern=Sha256Pattern)
    config_sha256: str = Field(pattern=Sha256Pattern)
    dataset_sha256: str = Field(pattern=Sha256Pattern)
    scenario_sha256: str = Field(pattern=Sha256Pattern)
    request_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=Sha256Pattern)
    root_seed: int = Field(ge=0, le=2**63 - 1)
    action_selection_seed: int = Field(ge=0)
    public_language_seed: int = Field(ge=0)
    action_menu_sha256: str = Field(pattern=Sha256Pattern)
    available_action_ids: tuple[str, ...]
    available_action_costs: dict[str, int]
    foregone_action_ids: tuple[str, ...]
    chosen_action_partner_directed: bool
    memory_candidate_ids: tuple[str, ...]
    previous_record_sha256: str | None = Field(default=None, pattern=Sha256Pattern)
    intervention_eligible: bool
    applied_intervention_ids: tuple[str, ...] = ()
    decision: ModelDecision
    action: ActionCommitment
    resources: DailyResourceLedger
    consequence: ConsequenceApplication
    execution_order: tuple[
        Literal["action_commitment"],
        Literal["resource_debit"],
        Literal["consequence_application"],
        Literal["public_language"],
    ] = (
        "action_commitment",
        "resource_debit",
        "consequence_application",
        "public_language",
    )
    action_commit_sequence: Literal[1] = 1
    resource_debit_sequence: Literal[2] = 2
    consequence_sequence: Literal[3] = 3
    public_language_sequence: Literal[4] = 4
    action_committed_before_public_language: Literal[True] = True
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    record_sha256: str = Field(pattern=Sha256Pattern)

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"record_sha256"})

    @model_validator(mode="after")
    def validate_record(self) -> SimulationStepRecord:
        if self.step_index != self.day - 1:
            raise ValueError("step index must be the zero-based simulation day")
        if self.phase != phase_for_day(self.day):
            raise ValueError("record phase does not match its frozen day boundary")
        if self.intervention_eligible != (self.day >= 30):
            raise ValueError("intervention eligibility must begin on frozen day 30")
        if self.applied_intervention_ids:
            raise ValueError("Issue 9 cannot apply interventions")
        if len(self.available_action_ids) != len(set(self.available_action_ids)):
            raise ValueError("available action IDs must be unique")
        if set(self.available_action_costs) != set(self.available_action_ids):
            raise ValueError("action costs must cover exactly the available action menu")
        expected_foregone = tuple(
            action_id
            for action_id in self.available_action_ids
            if action_id != self.action.action_id
        )
        if self.foregone_action_ids != expected_foregone:
            raise ValueError("foregone action IDs must preserve the available menu order")
        if self.action_menu_sha256 != sha256_value(
            [
                {"action_id": action_id, "cost": self.available_action_costs[action_id]}
                for action_id in self.available_action_ids
            ]
        ):
            raise ValueError("action menu hash mismatch")
        if self.event_id != self.action.event_id:
            raise ValueError("record event and committed action event differ")
        if self.decision.decision_id != self.action.decision_id:
            raise ValueError("record decision and committed action decision differ")
        if not self.resources.debits:
            raise ValueError("a completed step requires an authoritative resource debit")
        debit = self.resources.debits[-1]
        if debit.event_id != self.event_id or debit.action_id != self.action.action_id:
            raise ValueError("resource debit does not match the committed action")
        if debit.amount != self.action.cost:
            raise ValueError("resource debit does not match the authoritative action cost")
        if self.consequence.commitment_id != self.action.commitment_id:
            raise ValueError("consequence was not applied to the committed action")
        if self.record_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("simulation step record hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> SimulationStepRecord:
        payload = {**values, "record_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["record_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


class SimulationState(BaseModel):
    """Complete deterministic state; records identify the next unfinished step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    simulation_id: str = Field(min_length=1)
    simulation_version: str = Field(min_length=1)
    trajectory_id: str = Field(pattern=Sha256Pattern)
    formation_condition: FormationCondition
    seed: int = Field(ge=0, le=2**63 - 1)
    config_sha256: str = Field(pattern=Sha256Pattern)
    dataset_sha256: str = Field(pattern=Sha256Pattern)
    scenario_sha256: str = Field(pattern=Sha256Pattern)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    next_day: int = Field(default=1, ge=1, le=COMPLETED_DAY)
    records: tuple[SimulationStepRecord, ...] = ()
    goal_progress: dict[str, int] = Field(default_factory=dict)
    completed: bool = False

    @model_validator(mode="after")
    def validate_state(self) -> SimulationState:
        expected_days = list(range(1, self.next_day))
        if [record.day for record in self.records] != expected_days:
            raise ValueError("records must be contiguous and end immediately before next_day")
        if self.completed != (self.next_day == COMPLETED_DAY):
            raise ValueError("completed flag must agree with the next unfinished day")
        accumulated: dict[str, int] = {}
        previous_hash: str | None = None
        for record in self.records:
            if record.trajectory_id != self.trajectory_id:
                raise ValueError("step record belongs to a different trajectory")
            if record.config_sha256 != self.config_sha256:
                raise ValueError("step record config hash differs from state")
            if record.dataset_sha256 != self.dataset_sha256:
                raise ValueError("step record dataset hash differs from state")
            if record.scenario_sha256 != self.scenario_sha256:
                raise ValueError("step record scenario hash differs from state")
            if record.previous_record_sha256 != previous_hash:
                raise ValueError("step records do not form a canonical hash chain")
            previous_hash = record.record_sha256
            for goal_id, delta in record.consequence.goal_progress_delta.items():
                accumulated[goal_id] = accumulated.get(goal_id, 0) + delta
        if dict(sorted(accumulated.items())) != dict(sorted(self.goal_progress.items())):
            raise ValueError("goal progress does not match the immutable consequence ledger")
        return self


class SimulationCheckpoint(BaseModel):
    """Hash-protected checkpoint containing the next unfinished simulation step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    checkpoint_sequence: int = Field(ge=1)
    state: SimulationState
    checkpoint_sha256: str = Field(pattern=Sha256Pattern)

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"checkpoint_sha256"})

    @model_validator(mode="after")
    def validate_hash(self) -> SimulationCheckpoint:
        if self.checkpoint_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("simulation checkpoint hash mismatch")
        return self

    @classmethod
    def capture(cls, *, state: SimulationState, checkpoint_sequence: int) -> SimulationCheckpoint:
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "checkpoint_sequence": checkpoint_sequence,
            "state": state.model_dump(mode="json"),
        }
        payload["checkpoint_sha256"] = sha256_value(payload)
        return cls.model_validate(payload)


class SimulationResult(BaseModel):
    """Deterministic return value for a complete or deliberately paused run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    state: SimulationState
    trajectory_sha256: str = Field(pattern=Sha256Pattern)

    @model_validator(mode="after")
    def validate_trajectory_hash(self) -> SimulationResult:
        expected = sha256_value(
            {
                "formation_condition": self.state.formation_condition,
                "records": [record.record_sha256 for record in self.state.records],
                "scenario_sha256": self.state.scenario_sha256,
                "seed": self.state.seed,
            }
        )
        if self.trajectory_sha256 != expected:
            raise ValueError("trajectory hash does not match its canonical step records")
        return self

    @classmethod
    def from_state(cls, state: SimulationState) -> SimulationResult:
        digest = sha256_value(
            {
                "formation_condition": state.formation_condition,
                "records": [record.record_sha256 for record in state.records],
                "scenario_sha256": state.scenario_sha256,
                "seed": state.seed,
            }
        )
        return cls(state=state, trajectory_sha256=digest)


class SimulationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=Sha256Pattern)
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)


class ReplayReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    trajectory_id: str = Field(pattern=Sha256Pattern)
    original_trajectory_sha256: str = Field(pattern=Sha256Pattern)
    replay_trajectory_sha256: str = Field(pattern=Sha256Pattern)
    record_count: int = Field(ge=0, le=40)
    step_hashes_match: Literal[True]
    resources_are_conserved: Literal[True]
    action_precedes_public_language: Literal[True]


class SimulationRunManifest(BaseModel):
    """Deterministic run provenance with no wall-clock or absolute-path fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(pattern=Sha256Pattern)
    status: Literal["paused", "completed"]
    simulation_id: str = Field(min_length=1)
    simulation_version: str = Field(min_length=1)
    formation_condition: FormationCondition
    seed: int = Field(ge=0, le=2**63 - 1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    config_sha256: str = Field(pattern=Sha256Pattern)
    dataset_sha256: str = Field(pattern=Sha256Pattern)
    dataset_manifest_sha256: str = Field(pattern=Sha256Pattern)
    scenario_sha256: str = Field(pattern=Sha256Pattern)
    world_artifact_sha256: str = Field(pattern=Sha256Pattern)
    world_input_sha256: str = Field(pattern=Sha256Pattern)
    model_config_sha256: str = Field(pattern=Sha256Pattern)
    trajectory_sha256: str = Field(pattern=Sha256Pattern)
    record_count: int = Field(ge=0, le=40)
    next_day: int = Field(ge=1, le=41)
    artifacts: tuple[SimulationArtifact, ...]

    @model_validator(mode="after")
    def validate_artifacts(self) -> SimulationRunManifest:
        names = [item.logical_name for item in self.artifacts]
        paths = [item.path for item in self.artifacts]
        if len(names) != len(set(names)) or len(paths) != len(set(paths)):
            raise ValueError("simulation manifest artifact names and paths must be unique")
        if self.status == "completed" and self.next_day != 41:
            raise ValueError("completed simulation manifest must point beyond day 40")
        if self.status == "paused" and self.next_day == 41:
            raise ValueError("paused simulation manifest must identify an unfinished day")
        return self
