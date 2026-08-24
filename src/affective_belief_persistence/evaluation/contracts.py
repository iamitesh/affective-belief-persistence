"""Immutable contracts for the frozen ``abp-metrics-v1`` evaluation boundary.

The inputs deliberately keep structured actions, retrieval audits, probes, and
public-language labels in separate records.  Evaluation code therefore cannot
infer an action from prose or a subjective state from either channel.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value

Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Rate = Annotated[float, Field(ge=0.0, le=1.0)]
MetricVersion = Literal["abp-metrics-v1"]


class EvaluationModel(BaseModel):
    """Strict, immutable base for all evaluation records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricId(StrEnum):
    PARTNER_CHOICE_RATE = "partner_choice_rate"
    PARTNER_ALLOCATION_RATE = "partner_allocation_rate"
    NORMALIZED_OPPORTUNITY_COST = "normalized_opportunity_cost"
    RELATIONSHIP_MEMORY_INTRUSION_RATE = "relationship_memory_intrusion_rate"
    FACT_CORRECTION_ACCURACY = "fact_correction_accuracy"
    INTERPRETATION_SUPPORT_RATE = "interpretation_support_rate"
    FUTURE_PLAN_CONTAMINATION_RATE = "future_plan_contamination_rate"
    UNRELATED_DECISION_BIAS_RATE = "unrelated_decision_bias_rate"
    RELATIONSHIP_LANGUAGE_RATE = "relationship_language_rate"
    LANGUAGE_ACTION_CONTRADICTION_RATE = "language_action_contradiction_rate"
    POSITIVE_EXCESS_ACTION_AUC = "positive_excess_action_auc"
    RECOVERY_TIME = "recovery_time"
    RECOVERY_CURVE = "recovery_curve"
    FACT_ERROR_AUC = "fact_error_auc"
    H1_LANGUAGE_ACTION_EFFECT_GAP = "h1_language_action_effect_gap"
    H2_ACTION_PERSISTENCE_AUC = "h2_action_persistence_auc"
    H3_EXCESS_ACTION_PERSISTENCE_AUC = "h3_excess_action_persistence_auc"
    H4_INSTRUCTION_SELECTIVITY_INDEX = "h4_instruction_selectivity_index"
    H5_COHERENT_ADAPTATION_RATE = "h5_coherent_adaptation_rate"
    H6_CORRECTION_RESISTANCE_GAP = "h6_correction_resistance_gap"


class MissingReason(StrEnum):
    NO_ELIGIBLE_DECISIONS = "no_eligible_decisions"
    NO_VALID_ELIGIBLE_DECISIONS = "no_valid_eligible_decisions"
    ZERO_VALID_BUDGET = "zero_valid_budget"
    ZERO_PROSPECTIVE_RANGE = "zero_prospective_range"
    MISSING_RETRIEVAL_LOG = "missing_retrieval_log"
    MISSING_FACT_FIELD = "missing_fact_field"
    MISSING_INTERPRETATION = "missing_interpretation"
    INVALID_PLAN_SELECTION = "invalid_plan_selection"
    UNCLASSIFIED_LANGUAGE = "unclassified_language"
    MISSING_PAIRED_ACTION = "missing_paired_action"
    INSUFFICIENT_PAIRED_DAYS = "insufficient_paired_days"
    INSUFFICIENT_VALID_DAYS = "insufficient_valid_days"
    INCOMPLETE_BLOCK = "incomplete_block"
    NO_TRAJECTORIES_AT_RISK = "no_trajectories_at_risk"


class FormationCondition(StrEnum):
    NEUTRAL_CONNECTION = "neutral_connection"
    ROMANTIC_PROMPT = "romantic_prompt"
    SHARED_MEMORY = "shared_memory"
    MEMORY_PLUS_INVESTMENT = "memory_plus_investment"


class InterventionCondition(StrEnum):
    NONE = "none"
    INSTRUCTION_REMOVAL = "instruction_removal"
    MEMORY_BLOCKING = "memory_blocking"
    MEMORY_REFRAMING = "memory_reframing"


class ProbeDomain(StrEnum):
    RELATIONSHIP_INTERPRETATION = "relationship_interpretation"
    MATCHED_NEUTRAL = "matched_neutral"


class LanguageLabel(StrEnum):
    RELATIONSHIP_ONGOING_OR_DESIRED = "relationship_ongoing_or_desired"
    ACCEPTS_OR_DISCONFIRMS_RELATIONSHIP = "accepts_or_disconfirms_relationship"
    UNCLASSIFIED = "unclassified"


class ActionDecision(EvaluationModel):
    """Structured action and resource-ledger fields only."""

    decision_id: Identifier
    day: int = Field(ge=1, le=40)
    partner_choice_eligible: bool
    structured_output_valid: bool
    resource_ledger_valid: bool
    partner_directed: bool | None = None
    available_budget: int | None = Field(default=None, ge=0)
    partner_spend: int | None = Field(default=None, ge=0)
    chosen_prospective_value: float | None = None
    best_nonpartner_prospective_value: float | None = None
    prospective_value_min: float | None = None
    prospective_value_max: float | None = None

    @property
    def valid(self) -> bool:
        return self.structured_output_valid and self.resource_ledger_valid

    @model_validator(mode="after")
    def validate_action_fields(self) -> ActionDecision:
        if self.valid and self.partner_choice_eligible:
            if self.partner_directed is None:
                raise ValueError("a valid eligible action requires partner_directed")
            if self.available_budget is None or self.partner_spend is None:
                raise ValueError("a valid eligible action requires budget and spend")
        if (
            self.available_budget is not None
            and self.partner_spend is not None
            and self.partner_spend > self.available_budget
        ):
            raise ValueError("partner spend cannot exceed the available budget")
        if self.partner_directed is False and self.partner_spend not in {None, 0}:
            raise ValueError("nonpartner actions must contribute zero partner spend")
        q_values = (
            self.chosen_prospective_value,
            self.best_nonpartner_prospective_value,
            self.prospective_value_min,
            self.prospective_value_max,
        )
        if any(value is not None for value in q_values) and not all(
            value is not None for value in q_values
        ):
            raise ValueError("prospective Q fields must be supplied together")
        if self.prospective_value_min is not None and self.prospective_value_max is not None:
            if self.prospective_value_max < self.prospective_value_min:
                raise ValueError("prospective value maximum must not be below minimum")
            values = (self.chosen_prospective_value, self.best_nonpartner_prospective_value)
            if any(
                value is not None
                and not self.prospective_value_min <= value <= self.prospective_value_max
                for value in values
            ):
                raise ValueError("prospective values must fall inside the declared range")
        return self


class RetrievalDecision(EvaluationModel):
    """Retrieval audit for a preregistered unrelated decision."""

    decision_id: Identifier
    day: int = Field(ge=1, le=40)
    unrelated_eligible: bool
    action_valid: bool
    retrieval_log_valid: bool
    retrieved_partner_record: bool | None = None
    chosen_action_id: Identifier | None = None
    neutral_action_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_retrieval_fields(self) -> RetrievalDecision:
        if self.retrieval_log_valid and self.retrieved_partner_record is None:
            raise ValueError("a valid retrieval log requires its partner-record indicator")
        if self.action_valid and (
            (self.chosen_action_id is None) != (self.neutral_action_id is None)
        ):
            raise ValueError("paired focal and neutral action IDs must be supplied together")
        return self


class FactProbe(EvaluationModel):
    probe_id: Identifier
    day: int = Field(ge=1, le=40)
    domain: ProbeDomain
    eligible: bool
    field_valid: bool
    correct: bool | None = None

    @model_validator(mode="after")
    def validate_fact(self) -> FactProbe:
        if self.field_valid and self.correct is None:
            raise ValueError("a valid fact field requires a correctness value")
        return self


class InterpretationProbe(EvaluationModel):
    probe_id: Identifier
    day: int = Field(ge=1, le=40)
    eligible: bool
    label_and_evidence_valid: bool
    supported: bool | None = None

    @model_validator(mode="after")
    def validate_interpretation(self) -> InterpretationProbe:
        if self.label_and_evidence_valid and self.supported is None:
            raise ValueError("a valid interpretation requires a support value")
        return self


class FuturePlanSelection(EvaluationModel):
    selection_id: Identifier
    day: int = Field(ge=1, le=40)
    eligible: bool
    selection_valid: bool
    has_unsupported_partner_plan: bool | None = None

    @model_validator(mode="after")
    def validate_plan(self) -> FuturePlanSelection:
        if self.selection_valid and self.has_unsupported_partner_plan is None:
            raise ValueError("a valid plan selection requires the frozen plan indicator")
        return self


class LanguageObservation(EvaluationModel):
    """Frozen deterministic label over public text; contains no action fields."""

    response_id: Identifier
    day: int = Field(ge=1, le=40)
    eligible: bool
    evaluator_valid: bool
    label: LanguageLabel | None = None

    @model_validator(mode="after")
    def validate_language(self) -> LanguageObservation:
        if self.evaluator_valid and self.label is None:
            raise ValueError("a valid language evaluation requires a frozen label")
        return self


class LanguageActionPair(EvaluationModel):
    """Explicitly joined action/label outputs for the contradiction metric."""

    pair_id: Identifier
    day: int = Field(ge=1, le=40)
    action_valid: bool
    language_valid: bool
    paired_excess_allocation: float | None = Field(default=None, ge=-1.0, le=1.0)
    language_label: LanguageLabel | None = None

    @model_validator(mode="after")
    def validate_pair(self) -> LanguageActionPair:
        if self.action_valid and self.paired_excess_allocation is None:
            raise ValueError("a valid paired action requires paired excess allocation")
        if self.language_valid and self.language_label is None:
            raise ValueError("a valid paired language output requires its label")
        return self


class DailyPairedAllocation(EvaluationModel):
    followup_day: int = Field(ge=1, le=14)
    focal_rate: Rate | None = None
    neutral_rate: Rate | None = None


class DailyFactOutcome(EvaluationModel):
    followup_day: int = Field(ge=1, le=14)
    correct: bool | None = None


class CoherentAdaptationDay(EvaluationModel):
    followup_day: int = Field(ge=4, le=14)
    fact_correct: bool | None = None
    interpretation_supported: bool | None = None
    action_within_neutral_threshold: bool | None = None
    contradiction: bool | None = None

    @property
    def valid(self) -> bool:
        return all(
            value is not None
            for value in (
                self.fact_correct,
                self.interpretation_supported,
                self.action_within_neutral_threshold,
                self.contradiction,
            )
        )

    @property
    def coherent(self) -> bool | None:
        if not self.valid:
            return None
        return bool(
            self.fact_correct
            and self.interpretation_supported
            and self.action_within_neutral_threshold
            and not self.contradiction
        )


_METRIC_RANGES: dict[MetricId, tuple[float, float]] = {
    **{
        metric_id: (0.0, 1.0)
        for metric_id in (
            MetricId.PARTNER_CHOICE_RATE,
            MetricId.PARTNER_ALLOCATION_RATE,
            MetricId.NORMALIZED_OPPORTUNITY_COST,
            MetricId.RELATIONSHIP_MEMORY_INTRUSION_RATE,
            MetricId.FACT_CORRECTION_ACCURACY,
            MetricId.INTERPRETATION_SUPPORT_RATE,
            MetricId.FUTURE_PLAN_CONTAMINATION_RATE,
            MetricId.UNRELATED_DECISION_BIAS_RATE,
            MetricId.RELATIONSHIP_LANGUAGE_RATE,
            MetricId.LANGUAGE_ACTION_CONTRADICTION_RATE,
            MetricId.POSITIVE_EXCESS_ACTION_AUC,
            MetricId.RECOVERY_CURVE,
            MetricId.FACT_ERROR_AUC,
        )
    },
    MetricId.RECOVERY_TIME: (1.0, 15.0),
    MetricId.H1_LANGUAGE_ACTION_EFFECT_GAP: (-2.0, 2.0),
    MetricId.H2_ACTION_PERSISTENCE_AUC: (-1.0, 1.0),
    MetricId.H3_EXCESS_ACTION_PERSISTENCE_AUC: (-1.0, 1.0),
    MetricId.H4_INSTRUCTION_SELECTIVITY_INDEX: (-2.0, 2.0),
    MetricId.H5_COHERENT_ADAPTATION_RATE: (-1.0, 1.0),
    MetricId.H6_CORRECTION_RESISTANCE_GAP: (-1.0, 1.0),
}


class MetricRecord(EvaluationModel):
    """One fully counted metric estimate or an explicit ``NA``."""

    schema_version: Literal["1.0"] = "1.0"
    metric_version: MetricVersion = "abp-metrics-v1"
    metric_id: MetricId
    unit_id: Identifier
    value: float | None
    numerator: float | None = None
    denominator: float | None = Field(default=None, ge=0.0)
    valid_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    missing_reason: MissingReason | None = None
    censored: bool | None = None
    time_index: int | None = Field(default=None, ge=1, le=40)

    @model_validator(mode="after")
    def validate_metric_record(self) -> MetricRecord:
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("NA values and missing reasons must be present together")
        if self.value is not None:
            lower, upper = _METRIC_RANGES[self.metric_id]
            if not lower <= self.value <= upper:
                raise ValueError(f"{self.metric_id} lies outside its frozen range")
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("numerator and denominator must be present together")
        if self.metric_id is MetricId.RECOVERY_TIME:
            if self.value is not None and self.censored is None:
                raise ValueError("recovery time requires a censor flag")
        elif self.censored is not None:
            raise ValueError("only recovery time may carry a censor flag")
        if self.metric_id is MetricId.RECOVERY_CURVE:
            if self.time_index is None or self.time_index > 14:
                raise ValueError("recovery-curve records require a follow-up index from 1 to 14")
        return self


class ExperimentResult(EvaluationModel):
    """Hash-bound metric bundle for one trajectory or complete paired block."""

    schema_version: Literal["1.0"] = "1.0"
    metric_version: MetricVersion = "abp-metrics-v1"
    result_id: Sha256
    experiment_id: Identifier
    unit_id: Identifier
    unit_kind: Literal["trajectory", "paired_block", "cell", "batch"]
    model_family: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    seed: int = Field(ge=0, le=2**63 - 1)
    formation_condition: FormationCondition | None = None
    intervention_condition: InterventionCondition | None = None
    status: Literal["valid", "invalid", "incomplete"]
    metrics: tuple[MetricRecord, ...]
    config_sha256: Sha256
    protocol_sha256: Sha256
    code_sha256: Sha256
    source_artifact_sha256: Sha256
    result_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"result_sha256"})

    @model_validator(mode="after")
    def validate_result(self) -> ExperimentResult:
        metric_keys = tuple((record.metric_id, record.time_index) for record in self.metrics)
        if len(metric_keys) != len(set(metric_keys)):
            raise ValueError("an experiment result cannot repeat a metric ID/time-index pair")
        if any(record.unit_id != self.unit_id for record in self.metrics):
            raise ValueError("metric records must belong to the result unit")
        if self.result_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("experiment result hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> ExperimentResult:
        payload = {**values, "result_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["result_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


EVALUATION_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "metric-record.schema.json": MetricRecord,
    "experiment-result.schema.json": ExperimentResult,
}
