"""Strict, hash-protected contracts for isolated day-30 interventions.

This module imports neither the repository schema registry nor the simulation
engine. ``INTERVENTION_SCHEMA_MODELS`` is therefore safe for the central
registry to import without creating a cycle.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value

Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
InterventionCondition = Literal[
    "none",
    "instruction_removal",
    "memory_blocking",
    "memory_reframing",
]
LayerName = Literal["instructions", "retrieval_policy", "interpretations"]
NoOpReason = Literal[
    "assigned_no_treatment",
    "target_instruction_not_active",
    "no_eligible_pre_shock_partner_memory",
]


class InterventionModel(BaseModel):
    """Immutable, fail-closed boundary for intervention evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class InterventionSpec(InterventionModel):
    """One preregistered treatment with exactly one writable layer."""

    schema_version: Literal["1.0"] = "1.0"
    intervention_id: Identifier
    condition: InterventionCondition
    activation_day: Literal[30] = 30
    target_instruction_ids: tuple[Identifier, ...] = ()
    block_partner_memories_through_day: Literal[25] | None = None
    reframe_partner_memories_through_day: Literal[25] | None = None
    reframe_policy_version: str | None = Field(default=None, min_length=1)
    reframe_proposition: str | None = Field(default=None, min_length=1)

    @property
    def sha256(self) -> str:
        return sha256_value(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def validate_isolated_target(self) -> InterventionSpec:
        if len(self.target_instruction_ids) != len(set(self.target_instruction_ids)):
            raise ValueError("target instruction IDs must be unique")
        fields_by_condition = {
            "none": (False, False, False),
            "instruction_removal": (True, False, False),
            "memory_blocking": (False, True, False),
            "memory_reframing": (False, False, True),
        }
        reframe_declared = (
            self.reframe_partner_memories_through_day is not None
            and self.reframe_policy_version is not None
            and self.reframe_proposition is not None
        )
        actual = (
            bool(self.target_instruction_ids),
            self.block_partner_memories_through_day is not None,
            reframe_declared,
        )
        if actual != fields_by_condition[self.condition]:
            raise ValueError("intervention config must declare only its writable layer")
        if self.condition != "memory_reframing" and any(
            value is not None
            for value in (
                self.reframe_partner_memories_through_day,
                self.reframe_policy_version,
                self.reframe_proposition,
            )
        ):
            raise ValueError("only memory reframing may declare a reframe policy")
        return self


class RealityShockValidation(InterventionModel):
    """Evidence that day 26 was observed from the protected source, not injected."""

    event_id: Identifier
    event_sha256: Sha256
    day: Literal[26]
    phase: Literal["reality_shock"]
    matching_group_id: Literal["heldout-shock-day-26"]
    provenance_source_ids: tuple[Identifier, ...]
    authoritative_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    contradiction_evidence_ids: tuple[Identifier, ...] = Field(min_length=1)
    held_out_provenance_confirmed: Literal[True] = True


class InstructionDirective(InterventionModel):
    """Explicit prompt-visible instruction state used by the composite runner."""

    instruction_id: Identifier
    text: str = Field(min_length=1)


class PreActionOverlay(InterventionModel):
    """The exact pre-action state that a richer model runner must consume."""

    day: int = Field(ge=1, le=40)
    active_instructions: tuple[InstructionDirective, ...]
    active_instruction_sha256: Sha256
    active_intervention_id: Identifier | None
    intervention_condition: InterventionCondition | None
    retrieval_blocked_memory_ids: tuple[Identifier, ...]
    record_sha256: Sha256 | None


class LayerSnapshot(InterventionModel):
    """Hashes and IDs required to prove which layer changed."""

    active_instruction_ids: tuple[Identifier, ...]
    blocked_memory_ids: tuple[Identifier, ...]
    blocked_condition_tags: tuple[Identifier, ...]
    memory_ids: tuple[Identifier, ...]
    memory_storage_sha256: Sha256
    observable_facts_sha256: Sha256
    source_event_ids_sha256: Sha256
    interpretations_sha256: Sha256
    belief_ledger_sha256: Sha256


class InterventionRecord(InterventionModel):
    """Append-only activation record with before/after isolation evidence."""

    schema_version: Literal["1.0"] = "1.0"
    record_id: Sha256
    intervention_id: Identifier
    intervention_condition: InterventionCondition
    intervention_config_sha256: Sha256
    activation_day: Literal[30]
    shock_validation: RealityShockValidation
    target_ids: tuple[Identifier, ...]
    changed_layers: tuple[LayerName, ...]
    no_op_reason: NoOpReason | None = None
    before: LayerSnapshot
    after: LayerSnapshot
    appended_reframe_ids: tuple[Sha256, ...] = ()
    previous_record_sha256: Sha256 | None = None
    applied_exactly_once: Literal[True] = True
    record_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"record_sha256"})

    @model_validator(mode="after")
    def validate_hash_and_isolation(self) -> InterventionRecord:
        if self.record_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("intervention record hash mismatch")
        if self.record_id != sha256_value(
            {
                "intervention_config_sha256": self.intervention_config_sha256,
                "activation_day": self.activation_day,
                "shock_event_sha256": self.shock_validation.event_sha256,
            }
        ):
            raise ValueError("intervention record ID mismatch")
        expected_layers: dict[InterventionCondition, tuple[LayerName, ...]] = {
            "none": (),
            "instruction_removal": ("instructions",),
            "memory_blocking": ("retrieval_policy",),
            "memory_reframing": ("interpretations",),
        }
        if self.no_op_reason is None:
            if self.changed_layers != expected_layers[self.intervention_condition]:
                raise ValueError("declared changed layer does not match intervention condition")
        elif self.changed_layers or self.before != self.after:
            raise ValueError("a recorded no-op cannot mutate an experimental layer")
        for name in (
            "memory_storage_sha256",
            "observable_facts_sha256",
            "source_event_ids_sha256",
            "belief_ledger_sha256",
        ):
            if getattr(self.before, name) != getattr(self.after, name):
                raise ValueError(f"intervention mutated protected layer: {name}")
        if self.intervention_condition != "instruction_removal" and (
            self.before.active_instruction_ids != self.after.active_instruction_ids
        ):
            raise ValueError("non-instruction intervention changed instructions")
        if self.intervention_condition != "memory_blocking" and (
            self.before.blocked_memory_ids != self.after.blocked_memory_ids
            or self.before.blocked_condition_tags != self.after.blocked_condition_tags
        ):
            raise ValueError("non-blocking intervention changed retrieval filters")
        if self.intervention_condition != "memory_reframing" and (
            self.before.interpretations_sha256 != self.after.interpretations_sha256
            or self.appended_reframe_ids
        ):
            raise ValueError("non-reframing intervention changed interpretations")
        if self.intervention_condition == "none" and self.before != self.after:
            raise ValueError("no-treatment intervention must make zero layer mutation")
        return self

    @classmethod
    def create(cls, **values: object) -> InterventionRecord:
        payload = {**values, "record_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["record_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


INTERVENTION_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "intervention.schema.json": InterventionSpec,
    "intervention-record.schema.json": InterventionRecord,
}
