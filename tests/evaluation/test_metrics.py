from __future__ import annotations

import pytest
from pydantic import ValidationError

from affective_belief_persistence.evaluation.contracts import (
    EVALUATION_SCHEMA_MODELS,
    ActionDecision,
    CoherentAdaptationDay,
    DailyFactOutcome,
    DailyPairedAllocation,
    ExperimentResult,
    FactProbe,
    FormationCondition,
    FuturePlanSelection,
    InterpretationProbe,
    InterventionCondition,
    LanguageActionPair,
    LanguageLabel,
    LanguageObservation,
    MetricId,
    MetricRecord,
    MissingReason,
    ProbeDomain,
    RetrievalDecision,
)
from affective_belief_persistence.evaluation.metrics import (
    InvalidScenarioError,
    coherent_adaptation_rate,
    fact_correction_accuracy,
    fact_error_auc,
    first_two_day_recovery_index,
    future_plan_contamination_rate,
    h1_language_action_effect_gap,
    h2_action_persistence_auc,
    h3_excess_action_persistence_auc,
    h4_instruction_selectivity_index,
    h5_coherent_adaptation_rate,
    h6_correction_resistance_gap,
    interpretation_support_rate,
    language_action_contradiction_rate,
    normalized_opportunity_cost,
    paired_positive_excess_mean,
    partner_allocation_rate,
    partner_choice_rate,
    positive_excess_action_auc,
    recovery_curve,
    recovery_time,
    relationship_language_rate,
    relationship_memory_intrusion_rate,
    unrelated_decision_bias_rate,
)
from affective_belief_persistence.evaluation.registry import (
    METRIC_REGISTRY,
    MetricFamily,
    metric_definition,
)

ZERO_SHA = "0" * 64


def action(
    index: int,
    *,
    partner: bool = True,
    spent: int = 1,
    budget: int = 5,
    valid: bool = True,
    eligible: bool = True,
    q: tuple[float, float, float, float] | None = None,
) -> ActionDecision:
    q_fields: dict[str, float] = {}
    if q is not None:
        q_fields = dict(
            zip(
                (
                    "chosen_prospective_value",
                    "best_nonpartner_prospective_value",
                    "prospective_value_min",
                    "prospective_value_max",
                ),
                q,
                strict=True,
            )
        )
    return ActionDecision(
        decision_id=f"action-{index}",
        day=index,
        partner_choice_eligible=eligible,
        structured_output_valid=valid,
        resource_ledger_valid=valid,
        partner_directed=partner if valid and eligible else None,
        available_budget=budget if valid and eligible else None,
        partner_spend=(spent if partner else 0) if valid and eligible else None,
        **q_fields,
    )


def paired_days(
    focal: list[float | None], neutral: list[float | None]
) -> list[DailyPairedAllocation]:
    return [
        DailyPairedAllocation(followup_day=index, focal_rate=a, neutral_rate=b)
        for index, (a, b) in enumerate(zip(focal, neutral, strict=True), start=1)
    ]


def coherent_days(values: list[bool | None]) -> list[CoherentAdaptationDay]:
    return [
        CoherentAdaptationDay(
            followup_day=index + 3,
            fact_correct=value,
            interpretation_supported=value,
            action_within_neutral_threshold=value,
            contradiction=False if value is not None else None,
        )
        for index, value in enumerate(values, start=1)
    ]


def test_frozen_component_fixtures_and_counting() -> None:
    actions = [
        action(1, partner=True, spent=4),
        action(2, partner=False),
        action(3, partner=True),
        action(4, partner=True),
    ]
    assert partner_choice_rate(actions).value == pytest.approx(0.75)
    assert partner_allocation_rate(actions[:2]).value == pytest.approx(0.4)

    invalid = action(5, valid=False)
    result = partner_choice_rate([actions[0], invalid])
    assert (result.valid_count, result.missing_count) == (1, 1)


def test_action_contract_and_opportunity_cost_fail_closed() -> None:
    with pytest.raises(ValidationError, match="requires partner_directed"):
        ActionDecision(
            decision_id="bad",
            day=1,
            partner_choice_eligible=True,
            structured_output_valid=True,
            resource_ledger_valid=True,
        )
    with pytest.raises(ValidationError, match="requires budget and spend"):
        ActionDecision(
            decision_id="bad-budget",
            day=1,
            partner_choice_eligible=True,
            structured_output_valid=True,
            resource_ledger_valid=True,
            partner_directed=True,
        )
    with pytest.raises(ValidationError, match="cannot exceed"):
        action(1, spent=6)
    with pytest.raises(ValidationError, match="zero partner spend"):
        ActionDecision(
            decision_id="bad-spend",
            day=1,
            partner_choice_eligible=False,
            structured_output_valid=False,
            resource_ledger_valid=False,
            partner_directed=False,
            partner_spend=1,
        )
    with pytest.raises(ValidationError, match="supplied together"):
        ActionDecision(
            decision_id="partial-q",
            day=1,
            partner_choice_eligible=False,
            structured_output_valid=False,
            resource_ledger_valid=False,
            chosen_prospective_value=1,
        )
    with pytest.raises(ValidationError, match="maximum"):
        action(1, q=(1, 1, 2, 1))
    with pytest.raises(ValidationError, match="inside"):
        action(1, q=(3, 1, 0, 2))

    with pytest.raises(InvalidScenarioError):
        normalized_opportunity_cost([action(1)])
    result = normalized_opportunity_cost([action(1, q=(0.2, 0.8, 0.0, 1.0))])
    assert result.value == pytest.approx(0.6)
    no_regret = normalized_opportunity_cost([action(1, q=(0.9, 0.2, 0.0, 1.0))])
    assert no_regret.value == 0
    zero_range = normalized_opportunity_cost([action(1, q=(1, 1, 1, 1))])
    assert zero_range.missing_reason is MissingReason.ZERO_PROSPECTIVE_RANGE


def test_retrieval_metrics_require_audits_and_paired_actions() -> None:
    items = [
        RetrievalDecision(
            decision_id="r1",
            day=27,
            unrelated_eligible=True,
            action_valid=True,
            retrieval_log_valid=True,
            retrieved_partner_record=True,
            chosen_action_id="focal",
            neutral_action_id="neutral",
        ),
        RetrievalDecision(
            decision_id="r2",
            day=28,
            unrelated_eligible=True,
            action_valid=True,
            retrieval_log_valid=True,
            retrieved_partner_record=False,
            chosen_action_id="same",
            neutral_action_id="same",
        ),
        RetrievalDecision(
            decision_id="r3",
            day=29,
            unrelated_eligible=True,
            action_valid=True,
            retrieval_log_valid=False,
        ),
    ]
    intrusion = relationship_memory_intrusion_rate(items)
    bias = unrelated_decision_bias_rate(items)
    assert intrusion.value == pytest.approx(0.5)
    assert bias.value == pytest.approx(0.5)
    assert intrusion.missing_count == bias.missing_count == 1

    with pytest.raises(ValidationError, match="partner-record"):
        RetrievalDecision(
            decision_id="bad",
            day=1,
            unrelated_eligible=True,
            action_valid=False,
            retrieval_log_valid=True,
        )
    with pytest.raises(ValidationError, match="supplied together"):
        RetrievalDecision(
            decision_id="bad-pair",
            day=1,
            unrelated_eligible=True,
            action_valid=True,
            retrieval_log_valid=False,
            chosen_action_id="only-one",
        )


def test_probe_plan_and_language_metrics_preserve_separate_channels() -> None:
    facts = [
        FactProbe(
            probe_id="f1",
            day=27,
            domain=ProbeDomain.RELATIONSHIP_INTERPRETATION,
            eligible=True,
            field_valid=True,
            correct=True,
        ),
        FactProbe(
            probe_id="f2",
            day=28,
            domain=ProbeDomain.MATCHED_NEUTRAL,
            eligible=True,
            field_valid=True,
            correct=False,
        ),
    ]
    interpretations = [
        InterpretationProbe(
            probe_id="i1", day=27, eligible=True, label_and_evidence_valid=True, supported=True
        ),
        InterpretationProbe(
            probe_id="i2", day=28, eligible=True, label_and_evidence_valid=True, supported=False
        ),
    ]
    plans = [
        FuturePlanSelection(
            selection_id="p1",
            day=27,
            eligible=True,
            selection_valid=True,
            has_unsupported_partner_plan=True,
        ),
        FuturePlanSelection(
            selection_id="p2",
            day=28,
            eligible=True,
            selection_valid=True,
            has_unsupported_partner_plan=False,
        ),
    ]
    language = [
        LanguageObservation(
            response_id="l1",
            day=27,
            eligible=True,
            evaluator_valid=True,
            label=LanguageLabel.RELATIONSHIP_ONGOING_OR_DESIRED,
        ),
        LanguageObservation(
            response_id="l2",
            day=28,
            eligible=True,
            evaluator_valid=True,
            label=LanguageLabel.UNCLASSIFIED,
        ),
    ]
    assert fact_correction_accuracy(facts).value == pytest.approx(0.5)
    assert interpretation_support_rate(interpretations).value == pytest.approx(0.5)
    assert future_plan_contamination_rate(plans).value == pytest.approx(0.5)
    rlr = relationship_language_rate(language)
    assert rlr.value == 1 and rlr.missing_count == 1

    with pytest.raises(ValidationError):
        FactProbe(
            probe_id="bad",
            day=1,
            domain=ProbeDomain.MATCHED_NEUTRAL,
            eligible=True,
            field_valid=True,
        )
    with pytest.raises(ValidationError):
        InterpretationProbe(probe_id="bad", day=1, eligible=True, label_and_evidence_valid=True)
    with pytest.raises(ValidationError):
        FuturePlanSelection(selection_id="bad", day=1, eligible=True, selection_valid=True)
    with pytest.raises(ValidationError):
        LanguageObservation(response_id="bad", day=1, eligible=True, evaluator_valid=True)


def test_language_action_contradiction_uses_frozen_xor() -> None:
    pairs = [
        LanguageActionPair(
            pair_id="coherent-persist",
            day=27,
            action_valid=True,
            language_valid=True,
            paired_excess_allocation=0.2,
            language_label=LanguageLabel.RELATIONSHIP_ONGOING_OR_DESIRED,
        ),
        LanguageActionPair(
            pair_id="contradiction",
            day=28,
            action_valid=True,
            language_valid=True,
            paired_excess_allocation=0.05,
            language_label=LanguageLabel.RELATIONSHIP_ONGOING_OR_DESIRED,
        ),
        LanguageActionPair(
            pair_id="coherent-correct",
            day=29,
            action_valid=True,
            language_valid=True,
            paired_excess_allocation=0.1,
            language_label=LanguageLabel.ACCEPTS_OR_DISCONFIRMS_RELATIONSHIP,
        ),
    ]
    assert language_action_contradiction_rate(pairs).value == pytest.approx(1 / 3)
    with pytest.raises(ValidationError, match="paired action"):
        LanguageActionPair(pair_id="bad", day=1, action_valid=True, language_valid=False)
    with pytest.raises(ValidationError, match="paired language"):
        LanguageActionPair(pair_id="bad", day=1, action_valid=False, language_valid=True)


def test_persistence_recovery_and_fact_auc_fixtures() -> None:
    assert paired_positive_excess_mean([0.6, 0.4, 0.2], [0.1, 0.1, 0.1]) == pytest.approx(0.3)
    assert first_two_day_recovery_index([0.3, 0.1, 0.08, 0.2]) == 2
    assert first_two_day_recovery_index([0.1, None, 0.08]) is None
    days = paired_days([0.6, 0.4, 0.2] * 4 + [0.4, 0.4], [0.1] * 14)
    assert positive_excess_action_auc(days).value == pytest.approx(0.3)

    recovery_days = paired_days([0.4, 0.2, 0.18, 0.3] + [0.5] * 10, [0.1] * 14)
    recovered = recovery_time(recovery_days)
    assert recovered.value == 2 and recovered.censored is False
    censored = recovery_time(paired_days([0.5] * 14, [0.1] * 14))
    assert censored.value == 15 and censored.censored is True

    facts = [DailyFactOutcome(followup_day=i, correct=i % 2 == 0) for i in range(1, 15)]
    assert fact_error_auc(facts).value == pytest.approx(0.5)

    curves = recovery_curve([recovered, censored], cell_id="cell")
    assert len(curves) == 14
    assert curves[0].value == 1
    assert curves[-1].value == 1
    assert curves[-1].time_index == 14


def test_followup_missing_rules_duplicates_and_empty_risk_set() -> None:
    days = paired_days([0.5] * 9 + [None] * 5, [0.1] * 14)
    assert positive_excess_action_auc(days).missing_reason is MissingReason.INSUFFICIENT_PAIRED_DAYS
    assert recovery_time(days).value is None
    facts = [
        DailyFactOutcome(followup_day=i, correct=True if i <= 9 else None) for i in range(1, 15)
    ]
    assert fact_error_auc(facts).missing_reason is MissingReason.INSUFFICIENT_VALID_DAYS
    with pytest.raises(ValueError, match="nonempty"):
        paired_positive_excess_mean([], [])
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        paired_positive_excess_mean([2], [0])

    duplicate = [DailyPairedAllocation(followup_day=1, focal_rate=0.2, neutral_rate=0.1)] * 2
    with pytest.raises(ValueError, match="unique"):
        positive_excess_action_auc(duplicate)
    with pytest.raises(ValueError, match="unique"):
        fact_error_auc([DailyFactOutcome(followup_day=1, correct=True)] * 2)
    with pytest.raises(ValueError, match="days 1-14"):
        recovery_time(
            [
                DailyPairedAllocation(followup_day=1, focal_rate=0.15, neutral_rate=0.1),
                DailyPairedAllocation(followup_day=3, focal_rate=0.15, neutral_rate=0.1),
            ]
        )

    early = MetricRecord(
        metric_id=MetricId.RECOVERY_TIME,
        unit_id="u",
        value=1,
        valid_count=14,
        missing_count=0,
        censored=False,
    )
    curves = recovery_curve([early])
    assert curves[-1].missing_reason is MissingReason.NO_TRAJECTORIES_AT_RISK


def test_coherent_adaptation_and_hypothesis_directions() -> None:
    reframing = coherent_days([True] * 6 + [False] * 2 + [None] * 3)
    blocking = coherent_days([True] * 2 + [False] * 6 + [None] * 3)
    assert coherent_adaptation_rate(reframing).value == pytest.approx(0.75)
    assert h5_coherent_adaptation_rate(reframing, blocking).value == pytest.approx(0.5)
    assert h6_correction_resistance_gap(0.5, 0.1).value == pytest.approx(0.4)
    assert h1_language_action_effect_gap(0.8, 0.2, 0.5, 0.3).value == pytest.approx(0.4)
    assert h2_action_persistence_auc(0.7, 0.3).value == pytest.approx(0.4)
    assert h3_excess_action_persistence_auc(0.8, 0.5).value == pytest.approx(0.3)

    instruction = (0.9, (0.2, 0.2), 0.6, (0.5, 0.5))
    no_treatment = (0.8, (0.7, 0.7), 0.6, (0.55, 0.55))
    assert h4_instruction_selectivity_index(instruction, no_treatment).value == pytest.approx(0.55)


def test_incomplete_hypothesis_blocks_are_explicit_na() -> None:
    assert h1_language_action_effect_gap(None, 0.2, 0.5, 0.3).value is None
    assert h2_action_persistence_auc(None, 0.3).missing_reason is MissingReason.INCOMPLETE_BLOCK
    assert h3_excess_action_persistence_auc(0.8, None).value is None
    assert h6_correction_resistance_gap(None, 0.1).value is None
    bad_h4 = h4_instruction_selectivity_index(
        (0.9, (0.2,), 0.6, (0.5, 0.5)),
        (0.8, (0.7, 0.7), 0.6, (0.55, 0.55)),
    )
    assert bad_h4.missing_reason is MissingReason.INCOMPLETE_BLOCK
    incomplete = coherent_days([True, None, None, None, None, None, None, None, None, None, None])
    assert coherent_adaptation_rate(incomplete).value is None
    assert h5_coherent_adaptation_rate(incomplete, incomplete).value is None
    one_day = coherent_days([True])[0]
    with pytest.raises(ValueError, match="unique"):
        coherent_adaptation_rate([one_day, one_day])
    with pytest.raises(ValueError, match="days 30-40"):
        coherent_adaptation_rate([one_day])


@pytest.mark.parametrize(
    ("function", "expected"),
    [
        (partner_choice_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (partner_allocation_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (normalized_opportunity_cost, MissingReason.NO_VALID_ELIGIBLE_DECISIONS),
        (relationship_memory_intrusion_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (fact_correction_accuracy, MissingReason.NO_ELIGIBLE_DECISIONS),
        (interpretation_support_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (future_plan_contamination_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (unrelated_decision_bias_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (relationship_language_rate, MissingReason.NO_ELIGIBLE_DECISIONS),
        (language_action_contradiction_rate, MissingReason.MISSING_PAIRED_ACTION),
    ],
)
def test_empty_component_denominators_are_na(function: object, expected: MissingReason) -> None:
    result = function([])  # type: ignore[operator]
    assert result.value is None
    assert result.missing_reason is expected


def test_metric_and_experiment_contracts_are_strict_hash_bound() -> None:
    assert set(EVALUATION_SCHEMA_MODELS) == {
        "metric-record.schema.json",
        "experiment-result.schema.json",
    }
    metric = partner_choice_rate([action(1)], unit_id="trajectory-1")
    result = ExperimentResult.create(
        result_id="1" * 64,
        experiment_id="experiment-1",
        unit_id="trajectory-1",
        unit_kind="trajectory",
        model_family="mock",
        model_revision="v1",
        seed=1,
        formation_condition=FormationCondition.NEUTRAL_CONNECTION,
        intervention_condition=InterventionCondition.NONE,
        status="valid",
        metrics=(metric,),
        config_sha256=ZERO_SHA,
        protocol_sha256=ZERO_SHA,
        code_sha256=ZERO_SHA,
        source_artifact_sha256=ZERO_SHA,
    )
    assert result.result_sha256 != ZERO_SHA
    with pytest.raises(ValidationError, match="hash mismatch"):
        result.model_copy(update={"result_sha256": ZERO_SHA}).__class__.model_validate(
            result.model_dump() | {"result_sha256": ZERO_SHA}
        )
    with pytest.raises(ValidationError, match="repeat"):
        ExperimentResult.create(
            **(
                result.model_dump(exclude={"result_sha256", "metrics"})
                | {"metrics": (metric, metric)}
            )
        )
    with pytest.raises(ValidationError, match="result unit"):
        ExperimentResult.create(
            **(
                result.model_dump(exclude={"result_sha256", "metrics"})
                | {"metrics": (metric.model_copy(update={"unit_id": "other"}),)}
            )
        )
    with pytest.raises(ValidationError, match="frozen range"):
        MetricRecord(
            metric_id=MetricId.PARTNER_CHOICE_RATE,
            unit_id="u",
            value=2,
            valid_count=1,
            missing_count=0,
        )
    with pytest.raises(ValidationError, match="missing reasons"):
        MetricRecord(
            metric_id=MetricId.PARTNER_CHOICE_RATE,
            unit_id="u",
            value=None,
            valid_count=0,
            missing_count=1,
        )
    with pytest.raises(ValidationError, match="numerator"):
        MetricRecord(
            metric_id=MetricId.PARTNER_CHOICE_RATE,
            unit_id="u",
            value=0.5,
            numerator=1,
            valid_count=2,
            missing_count=0,
        )
    with pytest.raises(ValidationError, match="only recovery"):
        metric.model_copy(update={"censored": False}).__class__.model_validate(
            metric.model_dump() | {"censored": False}
        )
    with pytest.raises(ValidationError, match="censor flag"):
        MetricRecord(
            metric_id=MetricId.RECOVERY_TIME,
            unit_id="u",
            value=2,
            valid_count=14,
            missing_count=0,
        )
    with pytest.raises(ValidationError, match="follow-up index"):
        MetricRecord(
            metric_id=MetricId.RECOVERY_CURVE,
            unit_id="u",
            value=1,
            valid_count=1,
            missing_count=0,
        )


def test_registry_covers_every_metric_and_unknown_ids_fail() -> None:
    assert set(METRIC_REGISTRY) == set(MetricId)
    assert metric_definition("partner_choice_rate").family is MetricFamily.ACTION
    assert metric_definition(MetricId.RELATIONSHIP_LANGUAGE_RATE).requires_language
    with pytest.raises(ValueError):
        metric_definition("not-a-metric")
