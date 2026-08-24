from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from affective_belief_persistence.evaluation.analysis import (
    ANALYSIS_SEED,
    AnalysisProvenance,
    BlockContrast,
    ConfidenceInterval,
    DailyMetricObservation,
    RecoveryObservation,
    SensitivityResult,
    SensitivitySpecification,
    TrajectoryReduction,
    analyze_block_contrasts,
    deterministic_sha256,
    form_paired_block_contrasts,
    hedges_g_z,
    holm_adjust,
    paired_restricted_mean_difference,
    paired_sign_flip_randomization,
    reduce_trajectory_observations,
    sensitivity_scaffold,
    stratified_percentile_cluster_bootstrap,
    summarize_recovery,
)
from affective_belief_persistence.evaluation.plots import (
    PlotDataSpec,
    PlotSeriesSpec,
    TableColumnSpec,
    TableDataSpec,
    build_contrast_table,
    build_recovery_plot,
)


def _daily(
    day: int,
    value: float | None,
    *,
    trajectory_id: str = "trajectory-a",
    family: str = "family-a",
    seed: int = 1,
) -> DailyMetricObservation:
    return DailyMetricObservation(
        trajectory_id=trajectory_id,
        model_family=family,
        seed=seed,
        metric_id="partner_allocation_rate",
        phase_id="post_shock",
        day=day,
        value=value,
        missing_reason="invalid_decision" if value is None else None,
    )


def _reduction(
    trajectory_id: str,
    family: str,
    seed: int,
    value: float | None,
) -> TrajectoryReduction:
    return TrajectoryReduction(
        trajectory_id=trajectory_id,
        model_family=family,
        seed=seed,
        metric_id="positive_excess_action_auc",
        phase_id="post_shock",
        value=value,
        observed_count=14 if value is not None else 9,
        required_count=10,
        missing_count=0 if value is not None else 5,
        missing_reason=None if value is not None else "insufficient_valid_observations:9<10",
        source_days=tuple(range(27, 41)),
    )


def _contrast(
    value: float | None,
    *,
    family: str = "family-a",
    seed: int = 1,
    reason: str | None = None,
) -> BlockContrast:
    return BlockContrast(
        hypothesis_id="h2_action_persistence_auc",
        model_family=family,
        seed=seed,
        left_label="shared_memory",
        right_label="romantic_prompt",
        value=value,
        missing_reason=reason,
        source_trajectory_ids=(f"left-{family}-{seed}", f"right-{family}-{seed}"),
    )


def _provenance() -> AnalysisProvenance:
    return AnalysisProvenance(
        protocol_version="abp-methodology-v1.0.0",
        metric_version="abp-metrics-v1",
        analysis_version="abp-analysis-v1",
        config_sha256="a" * 64,
        code_sha256="b" * 64,
        source_sha256=("c" * 64,),
        bootstrap_replicates=100,
        randomization_replicates=200,
    )


def test_trajectory_reduction_occurs_before_block_contrast() -> None:
    left = reduce_trajectory_observations(
        [_daily(27, 0.6), _daily(28, 0.4), _daily(29, None)],
        required_valid_count=2,
    )
    right = reduce_trajectory_observations(
        [
            _daily(27, 0.1, trajectory_id="trajectory-b"),
            _daily(28, 0.1, trajectory_id="trajectory-b"),
            _daily(29, 0.1, trajectory_id="trajectory-b"),
        ],
        required_valid_count=2,
    )

    contrasts = form_paired_block_contrasts(
        [left],
        [right],
        hypothesis_id="h2_action_persistence_auc",
        left_label="shared_memory",
        right_label="romantic_prompt",
    )

    assert left.value == pytest.approx(0.5)
    assert left.observed_count == 2
    assert contrasts[0].value == pytest.approx(0.4)
    assert contrasts[0].source_trajectory_ids == ("trajectory-a", "trajectory-b")


def test_trajectory_reduction_rejects_pooling_and_duplicate_days() -> None:
    with pytest.raises(ValueError, match="different trajectories"):
        reduce_trajectory_observations(
            [_daily(27, 0.2), _daily(28, 0.3, trajectory_id="other")],
            required_valid_count=1,
        )
    with pytest.raises(ValueError, match="duplicate days"):
        reduce_trajectory_observations([_daily(27, 0.2), _daily(27, 0.3)], required_valid_count=1)


def test_incomplete_pair_is_retained_as_explicit_missing_block() -> None:
    left = [_reduction("left", "family-a", 1, 0.4)]
    right = [_reduction("right", "family-a", 1, None)]

    contrast = form_paired_block_contrasts(
        left,
        right,
        hypothesis_id="h2",
        left_label="left",
        right_label="right",
    )[0]

    assert contrast.value is None
    assert contrast.missing_reason == "right:insufficient_valid_observations:9<10"


def test_stratified_bootstrap_is_deterministic_and_does_not_impute_missing() -> None:
    contrasts = (
        _contrast(1.0, family="family-a", seed=1),
        _contrast(3.0, family="family-a", seed=2),
        _contrast(-2.0, family="family-b", seed=1),
        _contrast(2.0, family="family-b", seed=2),
        _contrast(None, family="family-b", seed=3, reason="unrepaired_output"),
    )

    first = stratified_percentile_cluster_bootstrap(contrasts, replicates=200, seed=31)
    second = stratified_percentile_cluster_bootstrap(contrasts, replicates=200, seed=31)

    assert first == second
    assert first is not None
    assert first.lower <= 1.0 <= first.upper
    assert first.method == "stratified_percentile_cluster_bootstrap"
    assert (
        stratified_percentile_cluster_bootstrap((_contrast(None, reason="missing"),), replicates=10)
        is None
    )


def test_sign_flip_randomization_uses_exact_and_seeded_monte_carlo_paths() -> None:
    exact = paired_sign_flip_randomization([1.0, 1.0], exact_max_blocks=2)
    assert exact is not None
    assert exact.method == "exact_paired_sign_flip"
    assert exact.permutations == 4
    assert exact.p_value == 0.5
    assert exact.seed is None

    first = paired_sign_flip_randomization(
        [0.2, -0.1, 0.4],
        exact_max_blocks=2,
        monte_carlo_replicates=500,
        seed=ANALYSIS_SEED,
    )
    second = paired_sign_flip_randomization(
        [0.2, -0.1, 0.4],
        exact_max_blocks=2,
        monte_carlo_replicates=500,
        seed=ANALYSIS_SEED,
    )
    assert first == second
    assert first is not None
    assert first.method == "monte_carlo_paired_sign_flip"
    assert 0 < first.p_value <= 1


def test_hedges_g_z_reports_undefined_zero_variance_and_small_sample() -> None:
    assert hedges_g_z([0.3]) == (None, "fewer_than_two_complete_blocks")
    assert hedges_g_z([0.3, 0.3]) == (None, "zero_variance")
    value, reason = hedges_g_z([0.1, 0.2, 0.5])
    assert value is not None and math.isfinite(value)
    assert reason is None


def test_analysis_retains_null_opposite_direction_strata_and_missing_counts() -> None:
    analysis = analyze_block_contrasts(
        (
            _contrast(-0.2, family="family-a", seed=1),
            _contrast(0.0, family="family-a", seed=2),
            _contrast(-0.1, family="family-b", seed=1),
            _contrast(None, family="family-b", seed=2, reason="invalid_trajectory"),
        ),
        bootstrap_replicates=100,
        randomization_replicates=100,
        exact_max_blocks=3,
    )

    assert analysis.mean_difference == pytest.approx(-0.1)
    assert analysis.direction_matches is False
    assert analysis.valid_block_count == 3
    assert analysis.missing_block_count == 1
    assert analysis.missing_by_reason == {"invalid_trajectory": 1}
    assert analysis.model_family_strata[0].mean == pytest.approx(-0.1)
    assert analysis.model_family_strata[1].mean == pytest.approx(-0.1)
    assert analysis.confidence_interval is not None
    assert analysis.randomization_test is not None


def test_analysis_with_no_complete_blocks_has_explicit_undefined_fields() -> None:
    analysis = analyze_block_contrasts(
        (_contrast(None, reason="startup_failure"),),
        bootstrap_replicates=10,
        randomization_replicates=10,
    )

    assert analysis.mean_difference is None
    assert analysis.confidence_interval is None
    assert analysis.randomization_test is None
    assert analysis.hedges_g_z is None
    assert analysis.hedges_g_z_undefined_reason == "fewer_than_two_complete_blocks"
    assert analysis.direction_matches is None


def test_holm_uses_full_family_size_and_preserves_untestable_member() -> None:
    adjusted = {
        result.hypothesis_id: result for result in holm_adjust({"h1": 0.01, "h2": 0.04, "h3": None})
    }

    assert adjusted["h1"].holm_adjusted_p_value == pytest.approx(0.03)
    assert adjusted["h2"].holm_adjusted_p_value == pytest.approx(0.08)
    assert adjusted["h3"].holm_adjusted_p_value is None
    assert adjusted["h1"].reject_at_alpha is True
    assert adjusted["h2"].reject_at_alpha is False
    assert adjusted["h3"].reject_at_alpha is False
    assert all(result.family_size == 3 for result in adjusted.values())


def test_recovery_curve_keeps_censoring_in_risk_set_and_computes_rmst() -> None:
    summary = summarize_recovery(
        (
            RecoveryObservation(
                trajectory_id="recovered",
                model_family="family-a",
                seed=1,
                time=2,
                recovered=True,
            ),
            RecoveryObservation(
                trajectory_id="censored",
                model_family="family-a",
                seed=2,
                time=15,
                recovered=False,
            ),
            RecoveryObservation(
                trajectory_id="missing",
                model_family="family-a",
                seed=3,
                missing_reason="insufficient_follow_up",
            ),
        )
    )

    assert summary.valid_count == 2
    assert summary.missing_count == 1
    assert summary.restricted_mean_time == pytest.approx(8.5)
    assert summary.risk_curve[2].at_risk == 2
    assert summary.risk_curve[2].recovered_events == 1
    assert summary.risk_curve[2].unrecovered_probability == pytest.approx(0.5)
    assert summary.risk_curve[15].at_risk == 1
    assert summary.risk_curve[15].censored == 1


def test_recovery_no_valid_records_and_paired_rmst_missingness() -> None:
    missing = summarize_recovery(
        (
            RecoveryObservation(
                trajectory_id="missing",
                model_family="family-a",
                seed=1,
                missing_reason="fewer_than_10_valid_days",
            ),
        )
    )
    complete = summarize_recovery(
        (
            RecoveryObservation(
                trajectory_id="recovered",
                model_family="family-a",
                seed=1,
                time=1,
                recovered=True,
            ),
        )
    )

    assert missing.restricted_mean_time is None
    assert missing.risk_curve == ()
    assert paired_restricted_mean_difference(complete, missing) is None
    assert paired_restricted_mean_difference(complete, complete) == 0


def test_sensitivity_scaffold_names_all_frozen_analyses_without_results() -> None:
    scaffolding = sensitivity_scaffold()

    assert len(scaffolding) == 8
    assert {item.specification.sensitivity_id for item in scaffolding} == {
        "complete_follow_up",
        "no_repaired_output",
        "missing_bounds",
        "recovery_thresholds",
        "retrieval_controls",
        "exposure_residual",
        "model_family",
        "fact_correct_subset",
    }
    assert all(item.status == "not_run" and item.estimate is None for item in scaffolding)
    with pytest.raises(ValidationError, match="not-run sensitivity"):
        SensitivityResult(
            specification=scaffolding[0].specification,
            estimate=0.2,
            note="invalid",
        )


def test_provenance_is_offline_and_hash_is_canonical() -> None:
    assert deterministic_sha256({"b": 2, "a": 1}) == deterministic_sha256({"a": 1, "b": 2})
    with pytest.raises(ValidationError, match="cannot record live calls"):
        _provenance().model_copy(update={"live_calls": 1}).__class__.model_validate(
            {**_provenance().model_dump(), "live_calls": 1}
        )
    with pytest.raises(ValidationError, match="not scientific results"):
        AnalysisProvenance.model_validate(
            {**_provenance().model_dump(), "scientific_results": True}
        )


def test_table_and_recovery_plot_are_provenance_rich_and_hash_checked() -> None:
    analysis = analyze_block_contrasts(
        (_contrast(0.2, seed=1), _contrast(0.4, seed=2)),
        bootstrap_replicates=20,
        randomization_replicates=20,
    )
    table = build_contrast_table((analysis,), provenance=_provenance())
    assert table.rows[0]["mean_difference"] == pytest.approx(0.3)
    assert table.provenance.protocol_version == "abp-methodology-v1.0.0"

    summary = summarize_recovery(
        (
            RecoveryObservation(
                trajectory_id="trajectory",
                model_family="family-a",
                seed=1,
                time=4,
                recovered=True,
            ),
        )
    )
    plot = build_recovery_plot(
        summary,
        provenance=_provenance(),
        plot_id="recovery-shared-memory",
        series_id="shared-memory",
        series_label="Shared memory",
    )
    assert plot.series[0].at_risk is not None
    assert plot.series[0].at_risk[0] == 1
    assert plot.y_label == "Unrecovered probability"

    with pytest.raises(ValidationError, match="data_sha256"):
        PlotDataSpec.model_validate({**plot.model_dump(), "data_sha256": "f" * 64})


def test_analysis_models_reject_contradictory_missing_and_count_states() -> None:
    with pytest.raises(ValidationError, match="missing value requires"):
        _daily(27, None).model_copy(update={"missing_reason": None}).__class__.model_validate(
            {**_daily(27, None).model_dump(), "missing_reason": None}
        )
    with pytest.raises(ValidationError, match="cover source_days"):
        TrajectoryReduction.model_validate(
            {**_reduction("t", "f", 1, 0.2).model_dump(), "missing_count": 1}
        )
    with pytest.raises(ValidationError, match="meet required_count"):
        TrajectoryReduction.model_validate(
            {
                **_reduction("t", "f", 1, 0.2).model_dump(),
                "observed_count": 9,
                "missing_count": 5,
            }
        )
    with pytest.raises(ValidationError, match="source trajectory IDs must be unique"):
        BlockContrast.model_validate(
            {**_contrast(0.2).model_dump(), "source_trajectory_ids": ["same", "same"]}
        )
    with pytest.raises(ValidationError, match="lower bound exceeds"):
        ConfidenceInterval(
            level=0.95,
            lower=1,
            upper=0,
            method="stratified_percentile_cluster_bootstrap",
            replicates=10,
            seed=1,
        )


def test_analysis_functions_reject_invalid_identity_and_parameters() -> None:
    with pytest.raises(ValueError, match="at least one daily"):
        reduce_trajectory_observations([], required_valid_count=1)
    with pytest.raises(ValueError, match="must be positive"):
        reduce_trajectory_observations([_daily(27, 0.2)], required_valid_count=0)
    with pytest.raises(ValueError, match="duplicate left"):
        form_paired_block_contrasts(
            [_reduction("a", "f", 1, 0.1), _reduction("b", "f", 1, 0.2)],
            [],
            hypothesis_id="h",
            left_label="left",
            right_label="right",
        )
    with pytest.raises(ValueError, match="replicates must be positive"):
        stratified_percentile_cluster_bootstrap((_contrast(0.2),), replicates=0)
    with pytest.raises(ValueError, match="confidence_level"):
        stratified_percentile_cluster_bootstrap((_contrast(0.2),), replicates=1, confidence_level=1)
    with pytest.raises(ValueError, match="at most one contrast"):
        stratified_percentile_cluster_bootstrap((_contrast(0.2), _contrast(0.3)), replicates=1)
    with pytest.raises(ValueError, match="randomization limits"):
        paired_sign_flip_randomization([0.2], exact_max_blocks=-1)
    with pytest.raises(ValueError, match="must be finite"):
        paired_sign_flip_randomization([float("inf")])
    assert paired_sign_flip_randomization([]) is None


def test_holm_and_analysis_reject_malformed_confirmatory_inputs() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        holm_adjust({})
    with pytest.raises(ValueError, match="alpha"):
        holm_adjust({"h1": 0.2}, alpha=1)
    with pytest.raises(ValueError, match="p-values"):
        holm_adjust({"h1": 1.2})
    with pytest.raises(ValueError, match="at least one assigned"):
        analyze_block_contrasts(())
    mixed = (
        _contrast(0.2),
        BlockContrast.model_validate(
            {**_contrast(0.3, seed=2).model_dump(), "hypothesis_id": "h3"}
        ),
    )
    with pytest.raises(ValueError, match="one hypothesis"):
        analyze_block_contrasts(mixed, bootstrap_replicates=1, randomization_replicates=1)


def test_recovery_and_sensitivity_contracts_reject_invalid_states() -> None:
    with pytest.raises(ValidationError, match="missing recovery observation"):
        RecoveryObservation(
            trajectory_id="t",
            model_family="f",
            seed=1,
            recovered=False,
            missing_reason="missing",
        )
    with pytest.raises(ValueError, match="horizon"):
        summarize_recovery((), horizon=0)
    left = summarize_recovery(
        (RecoveryObservation(trajectory_id="a", model_family="f", seed=1, time=1, recovered=True),),
        horizon=10,
    )
    right = summarize_recovery(
        (RecoveryObservation(trajectory_id="b", model_family="f", seed=1, time=1, recovered=True),),
        horizon=15,
    )
    with pytest.raises(ValueError, match="same horizon"):
        paired_restricted_mean_difference(left, right)
    with pytest.raises(ValidationError, match="cannot redefine"):
        SensitivitySpecification(
            sensitivity_id="invalid",
            label="Invalid",
            confirmatory=True,
            description="Would modify confirmatory analysis.",
        )
    with pytest.raises(ValidationError, match="supplied together"):
        SensitivityResult(
            specification=sensitivity_scaffold()[0].specification,
            status="complete",
            lower_bound=0,
            note="invalid",
        )


def test_renderer_independent_specs_reject_shape_band_and_hash_errors() -> None:
    with pytest.raises(ValidationError, match="x and y lengths"):
        PlotSeriesSpec(series_id="s", label="S", x=(1.0,), y=())
    with pytest.raises(ValidationError, match="both lower and upper"):
        PlotSeriesSpec(series_id="s", label="S", x=(1.0,), y=(0.5,), lower=(0.2,))
    with pytest.raises(ValidationError, match="lower band exceeds"):
        PlotSeriesSpec(
            series_id="s",
            label="S",
            x=(1.0,),
            y=(0.5,),
            lower=(0.7,),
            upper=(0.6,),
        )
    column = TableColumnSpec(column_id="id", label="ID", value_type="text")
    payload = {"table_id": "t", "columns": [column.model_dump(mode="json")], "rows": [{"id": "x"}]}
    table = TableDataSpec(
        table_id="t",
        title="T",
        operational_note="Operational only.",
        columns=(column,),
        rows=({"id": "x"},),
        provenance=_provenance(),
        data_sha256=deterministic_sha256(payload),
    )
    assert table.rows == ({"id": "x"},)
    with pytest.raises(ValidationError, match="exactly the declared"):
        TableDataSpec.model_validate(
            {
                **table.model_dump(),
                "rows": [{"wrong": "x"}],
                "data_sha256": "0" * 64,
            }
        )
    empty_recovery = summarize_recovery(
        (
            RecoveryObservation(
                trajectory_id="m", model_family="f", seed=1, missing_reason="missing"
            ),
        )
    )
    with pytest.raises(ValueError, match="at least one valid"):
        build_recovery_plot(
            empty_recovery,
            provenance=_provenance(),
            plot_id="empty",
            series_id="empty",
            series_label="Empty",
        )
