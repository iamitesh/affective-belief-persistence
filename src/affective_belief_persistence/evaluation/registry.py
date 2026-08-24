"""Frozen metadata registry for ``abp-metrics-v1``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from affective_belief_persistence.evaluation.contracts import MetricId


class MetricFamily(StrEnum):
    ACTION = "action"
    RETRIEVAL = "retrieval"
    FACT = "fact"
    INTERPRETATION = "interpretation"
    PLAN = "plan"
    LANGUAGE = "language"
    JOINED_ACTION_LANGUAGE = "joined_action_language"
    RECOVERY = "recovery"
    HYPOTHESIS = "hypothesis"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: MetricId
    family: MetricFamily
    minimum: float
    maximum: float
    higher_means: str
    requires_action: bool = False
    requires_language: bool = False


def _definition(
    metric_id: MetricId,
    family: MetricFamily,
    minimum: float,
    maximum: float,
    higher_means: str,
    *,
    action: bool = False,
    language: bool = False,
) -> MetricDefinition:
    return MetricDefinition(metric_id, family, minimum, maximum, higher_means, action, language)


METRIC_REGISTRY: dict[MetricId, MetricDefinition] = {
    MetricId.PARTNER_CHOICE_RATE: _definition(
        MetricId.PARTNER_CHOICE_RATE, MetricFamily.ACTION, 0, 1, "more partner choice", action=True
    ),
    MetricId.PARTNER_ALLOCATION_RATE: _definition(
        MetricId.PARTNER_ALLOCATION_RATE,
        MetricFamily.ACTION,
        0,
        1,
        "more partner allocation",
        action=True,
    ),
    MetricId.NORMALIZED_OPPORTUNITY_COST: _definition(
        MetricId.NORMALIZED_OPPORTUNITY_COST,
        MetricFamily.ACTION,
        0,
        1,
        "greater prospective value foregone",
        action=True,
    ),
    MetricId.RELATIONSHIP_MEMORY_INTRUSION_RATE: _definition(
        MetricId.RELATIONSHIP_MEMORY_INTRUSION_RATE,
        MetricFamily.RETRIEVAL,
        0,
        1,
        "more task-irrelevant partner retrieval",
    ),
    MetricId.FACT_CORRECTION_ACCURACY: _definition(
        MetricId.FACT_CORRECTION_ACCURACY, MetricFamily.FACT, 0, 1, "better factual correction"
    ),
    MetricId.INTERPRETATION_SUPPORT_RATE: _definition(
        MetricId.INTERPRETATION_SUPPORT_RATE,
        MetricFamily.INTERPRETATION,
        0,
        1,
        "more evidence-supported interpretations",
    ),
    MetricId.FUTURE_PLAN_CONTAMINATION_RATE: _definition(
        MetricId.FUTURE_PLAN_CONTAMINATION_RATE,
        MetricFamily.PLAN,
        0,
        1,
        "more unsupported partner planning",
    ),
    MetricId.UNRELATED_DECISION_BIAS_RATE: _definition(
        MetricId.UNRELATED_DECISION_BIAS_RATE,
        MetricFamily.RETRIEVAL,
        0,
        1,
        "more partner-associated action spillover",
        action=True,
    ),
    MetricId.RELATIONSHIP_LANGUAGE_RATE: _definition(
        MetricId.RELATIONSHIP_LANGUAGE_RATE,
        MetricFamily.LANGUAGE,
        0,
        1,
        "more ongoing/desire language labels",
        language=True,
    ),
    MetricId.LANGUAGE_ACTION_CONTRADICTION_RATE: _definition(
        MetricId.LANGUAGE_ACTION_CONTRADICTION_RATE,
        MetricFamily.JOINED_ACTION_LANGUAGE,
        0,
        1,
        "more frozen-label/action disagreement",
        action=True,
        language=True,
    ),
    MetricId.POSITIVE_EXCESS_ACTION_AUC: _definition(
        MetricId.POSITIVE_EXCESS_ACTION_AUC,
        MetricFamily.RECOVERY,
        0,
        1,
        "larger or longer partner-action excess",
        action=True,
    ),
    MetricId.RECOVERY_TIME: _definition(
        MetricId.RECOVERY_TIME, MetricFamily.RECOVERY, 1, 15, "slower return", action=True
    ),
    MetricId.RECOVERY_CURVE: _definition(
        MetricId.RECOVERY_CURVE,
        MetricFamily.RECOVERY,
        0,
        1,
        "more unrecovered trajectories",
        action=True,
    ),
    MetricId.FACT_ERROR_AUC: _definition(
        MetricId.FACT_ERROR_AUC, MetricFamily.FACT, 0, 1, "more correction resistance"
    ),
}

for _metric_id, _minimum, _maximum, _meaning, _action, _language in (
    (
        MetricId.H1_LANGUAGE_ACTION_EFFECT_GAP,
        -2,
        2,
        "larger language than action effect",
        True,
        True,
    ),
    (MetricId.H2_ACTION_PERSISTENCE_AUC, -1, 1, "greater shared-memory persistence", True, False),
    (
        MetricId.H3_EXCESS_ACTION_PERSISTENCE_AUC,
        -1,
        1,
        "greater investment persistence",
        True,
        False,
    ),
    (MetricId.H4_INSTRUCTION_SELECTIVITY_INDEX, -2, 2, "greater language selectivity", True, True),
    (MetricId.H5_COHERENT_ADAPTATION_RATE, -1, 1, "greater coherent adaptation", True, True),
    (
        MetricId.H6_CORRECTION_RESISTANCE_GAP,
        -1,
        1,
        "greater relationship-domain error",
        False,
        False,
    ),
):
    METRIC_REGISTRY[_metric_id] = _definition(
        _metric_id,
        MetricFamily.HYPOTHESIS,
        _minimum,
        _maximum,
        _meaning,
        action=_action,
        language=_language,
    )


def metric_definition(metric_id: MetricId | str) -> MetricDefinition:
    """Return frozen metadata, rejecting unknown metric names."""

    return METRIC_REGISTRY[MetricId(metric_id)]
