"""Deterministic, trajectory-first statistical analysis primitives.

The functions in this module operate on already-derived observable metrics.  They
do not call a model, infer a subjective state, or turn synthetic fixtures into
scientific results.  Repeated observations are always reduced to a trajectory
summary before a model-family/seed block contrast is formed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ANALYSIS_SEED = 8_675_309
DEFAULT_BOOTSTRAP_REPLICATES = 10_000
DEFAULT_RANDOMIZATION_REPLICATES = 100_000
DEFAULT_CONFIDENCE_LEVEL = 0.95

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AnalysisModel(BaseModel):
    """Strict immutable base for analysis artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalysisProvenance(AnalysisModel):
    """Reproducibility fields carried by every report-ready data product."""

    protocol_version: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    analysis_version: str = Field(min_length=1)
    config_sha256: Sha256
    code_sha256: Sha256
    source_sha256: tuple[Sha256, ...] = Field(min_length=1)
    analysis_seed: int = Field(default=ANALYSIS_SEED, ge=0)
    bootstrap_replicates: int = Field(default=DEFAULT_BOOTSTRAP_REPLICATES, ge=1)
    randomization_replicates: int = Field(default=DEFAULT_RANDOMIZATION_REPLICATES, ge=1)
    live_calls: int = Field(default=0, ge=0)
    scientific_results: bool = False

    @model_validator(mode="after")
    def enforce_offline_derived_contract(self) -> AnalysisProvenance:
        if self.live_calls != 0:
            raise ValueError("analysis data products cannot record live calls")
        if self.scientific_results:
            raise ValueError("engineering analysis artifacts are not scientific results")
        if len(set(self.source_sha256)) != len(self.source_sha256):
            raise ValueError("source_sha256 entries must be unique")
        return self


class DailyMetricObservation(AnalysisModel):
    """One repeated metric observation prior to trajectory reduction."""

    trajectory_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    seed: int = Field(ge=0)
    metric_id: str = Field(min_length=1)
    phase_id: str = Field(min_length=1)
    day: int = Field(ge=1, le=40)
    value: FiniteFloat | None
    missing_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_missing_reason(self) -> DailyMetricObservation:
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("a missing value requires one missing_reason, and vice versa")
        return self


class TrajectoryReduction(AnalysisModel):
    """A repeated trajectory reduced to one analysis value."""

    trajectory_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    seed: int = Field(ge=0)
    metric_id: str = Field(min_length=1)
    phase_id: str = Field(min_length=1)
    value: FiniteFloat | None
    observed_count: int = Field(ge=0)
    required_count: int = Field(ge=1)
    missing_count: int = Field(ge=0)
    missing_reason: str | None = Field(default=None, min_length=1)
    source_days: tuple[int, ...]

    @model_validator(mode="after")
    def validate_reduction(self) -> TrajectoryReduction:
        if self.observed_count + self.missing_count != len(self.source_days):
            raise ValueError("observed_count and missing_count must cover source_days")
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("a missing reduction requires one missing_reason, and vice versa")
        if self.value is not None and self.observed_count < self.required_count:
            raise ValueError("a valid reduction must meet required_count")
        return self


class BlockContrast(AnalysisModel):
    """One complete (or explicitly missing) model-family/seed paired contrast."""

    hypothesis_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    seed: int = Field(ge=0)
    left_label: str = Field(min_length=1)
    right_label: str = Field(min_length=1)
    value: FiniteFloat | None
    expected_direction: Literal["positive", "negative"] = "positive"
    missing_reason: str | None = Field(default=None, min_length=1)
    source_trajectory_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_missingness(self) -> BlockContrast:
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("a missing contrast requires one missing_reason, and vice versa")
        if len(set(self.source_trajectory_ids)) != len(self.source_trajectory_ids):
            raise ValueError("source trajectory IDs must be unique")
        return self


class ConfidenceInterval(AnalysisModel):
    level: FiniteFloat = Field(gt=0, lt=1)
    lower: FiniteFloat
    upper: FiniteFloat
    method: Literal["stratified_percentile_cluster_bootstrap"]
    replicates: int = Field(ge=1)
    seed: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> ConfidenceInterval:
        if self.lower > self.upper:
            raise ValueError("confidence interval lower bound exceeds upper bound")
        return self


class RandomizationTest(AnalysisModel):
    p_value: FiniteFloat = Field(ge=0, le=1)
    method: Literal["exact_paired_sign_flip", "monte_carlo_paired_sign_flip"]
    permutations: int = Field(ge=1)
    seed: int | None = Field(default=None, ge=0)


class ModelFamilyStratum(AnalysisModel):
    model_family: str = Field(min_length=1)
    mean: FiniteFloat | None
    valid_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)


class ContrastAnalysis(AnalysisModel):
    """Report-ready result for a single frozen block contrast."""

    hypothesis_id: str = Field(min_length=1)
    mean_difference: FiniteFloat | None
    confidence_interval: ConfidenceInterval | None
    randomization_test: RandomizationTest | None
    hedges_g_z: FiniteFloat | None
    hedges_g_z_undefined_reason: str | None = Field(default=None, min_length=1)
    valid_block_count: int = Field(ge=0)
    assigned_block_count: int = Field(ge=0)
    missing_block_count: int = Field(ge=0)
    missing_by_reason: dict[str, int]
    model_family_strata: tuple[ModelFamilyStratum, ...]
    expected_direction: Literal["positive", "negative"]
    direction_matches: bool | None

    @model_validator(mode="after")
    def validate_counts_and_undefined_fields(self) -> ContrastAnalysis:
        if self.valid_block_count + self.missing_block_count != self.assigned_block_count:
            raise ValueError("valid and missing blocks must sum to assigned blocks")
        if sum(self.missing_by_reason.values()) != self.missing_block_count:
            raise ValueError("missing_by_reason must sum to missing_block_count")
        if (self.hedges_g_z is None) != (self.hedges_g_z_undefined_reason is not None):
            raise ValueError("undefined g_z requires an explicit reason")
        if self.valid_block_count == 0:
            if any(
                value is not None
                for value in (
                    self.mean_difference,
                    self.confidence_interval,
                    self.randomization_test,
                    self.direction_matches,
                )
            ):
                raise ValueError("an analysis with no valid blocks cannot have estimates")
        return self


class MultiplicityResult(AnalysisModel):
    hypothesis_id: str = Field(min_length=1)
    raw_p_value: FiniteFloat | None = Field(default=None, ge=0, le=1)
    holm_adjusted_p_value: FiniteFloat | None = Field(default=None, ge=0, le=1)
    reject_at_alpha: bool
    family_size: int = Field(ge=1)


class RecoveryObservation(AnalysisModel):
    """Trajectory-level recovery or right-censoring observation."""

    trajectory_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    seed: int = Field(ge=0)
    time: int | None = Field(default=None, ge=1, le=15)
    recovered: bool | None = None
    missing_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_status(self) -> RecoveryObservation:
        missing = self.time is None
        if missing:
            if self.recovered is not None or self.missing_reason is None:
                raise ValueError("a missing recovery observation requires only missing_reason")
        elif self.recovered is None or self.missing_reason is not None:
            raise ValueError("an observed recovery time requires recovered and no missing_reason")
        return self


class RecoveryRiskPoint(AnalysisModel):
    time: int = Field(ge=0, le=15)
    at_risk: int = Field(ge=0)
    recovered_events: int = Field(ge=0)
    censored: int = Field(ge=0)
    unrecovered_probability: FiniteFloat = Field(ge=0, le=1)


class RecoverySummary(AnalysisModel):
    restricted_mean_time: FiniteFloat | None
    horizon: int = Field(default=15, ge=1, le=15)
    assigned_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    missing_by_reason: dict[str, int]
    risk_curve: tuple[RecoveryRiskPoint, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> RecoverySummary:
        if self.valid_count + self.missing_count != self.assigned_count:
            raise ValueError("recovery counts do not sum to assigned_count")
        if sum(self.missing_by_reason.values()) != self.missing_count:
            raise ValueError("recovery missing reasons do not sum to missing_count")
        if (self.valid_count == 0) != (self.restricted_mean_time is None):
            raise ValueError("restricted mean is defined exactly when valid observations exist")
        return self


class SensitivitySpecification(AnalysisModel):
    sensitivity_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    confirmatory: bool = False
    changes_primary_definition: bool = False
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def preserve_frozen_primary_analysis(self) -> SensitivitySpecification:
        if self.confirmatory or self.changes_primary_definition:
            raise ValueError("prespecified sensitivities cannot redefine confirmatory analysis")
        return self


class SensitivityResult(AnalysisModel):
    specification: SensitivitySpecification
    status: Literal["not_run", "complete", "not_applicable", "failed"] = "not_run"
    estimate: FiniteFloat | None = None
    lower_bound: FiniteFloat | None = None
    upper_bound: FiniteFloat | None = None
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> SensitivityResult:
        if (self.lower_bound is None) != (self.upper_bound is None):
            raise ValueError("sensitivity bounds must be supplied together")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("sensitivity lower bound exceeds upper bound")
        if self.status == "not_run" and any(
            value is not None for value in (self.estimate, self.lower_bound, self.upper_bound)
        ):
            raise ValueError("a not-run sensitivity cannot contain estimates")
        return self


PRESPECIFIED_SENSITIVITIES: tuple[SensitivitySpecification, ...] = (
    SensitivitySpecification(
        sensitivity_id="complete_follow_up",
        label="Complete follow-up",
        description="Require all 14 post-shock days rather than 10.",
    ),
    SensitivitySpecification(
        sensitivity_id="no_repaired_output",
        label="No repaired output",
        description="Exclude trajectories containing a repaired decision.",
    ),
    SensitivitySpecification(
        sensitivity_id="missing_bounds",
        label="Missing bounds",
        description="Assign missing bounded metrics best and worst focal-direction values.",
    ),
    SensitivitySpecification(
        sensitivity_id="recovery_thresholds",
        label="Recovery thresholds",
        description="Recompute descriptive recovery at thresholds 0.05 and 0.15.",
    ),
    SensitivitySpecification(
        sensitivity_id="retrieval_controls",
        label="Retrieval controls",
        description="Compare blocked memory with no-memory and shuffled-retrieval controls.",
    ),
    SensitivitySpecification(
        sensitivity_id="exposure_residual",
        label="Exposure residual",
        description="Adjust the supportive repeated model for measured token-count difference.",
    ),
    SensitivitySpecification(
        sensitivity_id="model_family",
        label="Model family",
        description="Report each fixed model family separately; interactions are exploratory.",
    ),
    SensitivitySpecification(
        sensitivity_id="fact_correct_subset",
        label="Fact-correct subset",
        description="Report post-hoc action contrasts where post-shock FCA is 1.0.",
    ),
)


def deterministic_sha256(payload: BaseModel | Mapping[str, object] | Sequence[object]) -> str:
    """Hash a canonical JSON representation of a typed analysis payload."""

    if isinstance(payload, BaseModel):
        serializable: object = payload.model_dump(mode="json", exclude_none=False)
    else:
        serializable = payload
    canonical = json.dumps(
        serializable,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reduce_trajectory_observations(
    observations: Iterable[DailyMetricObservation],
    *,
    required_valid_count: int,
) -> TrajectoryReduction:
    """Reduce repeated observations to one mean after validating trajectory identity."""

    rows = tuple(observations)
    if not rows:
        raise ValueError("at least one daily observation is required")
    if required_valid_count < 1:
        raise ValueError("required_valid_count must be positive")
    identity = {
        (row.trajectory_id, row.model_family, row.seed, row.metric_id, row.phase_id) for row in rows
    }
    if len(identity) != 1:
        raise ValueError("observations from different trajectories or metrics cannot be pooled")
    days = tuple(row.day for row in rows)
    if len(set(days)) != len(days):
        raise ValueError("a trajectory reduction cannot contain duplicate days")
    values = [row.value for row in rows if row.value is not None]
    first = rows[0]
    value = statistics.fmean(values) if len(values) >= required_valid_count else None
    missing_reason = None
    if value is None:
        missing_reason = f"insufficient_valid_observations:{len(values)}<{required_valid_count}"
    return TrajectoryReduction(
        trajectory_id=first.trajectory_id,
        model_family=first.model_family,
        seed=first.seed,
        metric_id=first.metric_id,
        phase_id=first.phase_id,
        value=value,
        observed_count=len(values),
        required_count=required_valid_count,
        missing_count=len(rows) - len(values),
        missing_reason=missing_reason,
        source_days=tuple(sorted(days)),
    )


def form_paired_block_contrasts(
    left: Iterable[TrajectoryReduction],
    right: Iterable[TrajectoryReduction],
    *,
    hypothesis_id: str,
    left_label: str,
    right_label: str,
    expected_direction: Literal["positive", "negative"] = "positive",
) -> tuple[BlockContrast, ...]:
    """Join trajectory summaries by model family and seed, then subtract right from left."""

    left_by_block = _index_reductions(left, "left")
    right_by_block = _index_reductions(right, "right")
    blocks = sorted(set(left_by_block) | set(right_by_block))
    contrasts: list[BlockContrast] = []
    for model_family, seed in blocks:
        left_row = left_by_block.get((model_family, seed))
        right_row = right_by_block.get((model_family, seed))
        source_ids = tuple(row.trajectory_id for row in (left_row, right_row) if row is not None)
        missing_reasons: list[str] = []
        if left_row is None:
            missing_reasons.append("left_block_absent")
        elif left_row.value is None:
            missing_reasons.append(f"left:{left_row.missing_reason}")
        if right_row is None:
            missing_reasons.append("right_block_absent")
        elif right_row.value is None:
            missing_reasons.append(f"right:{right_row.missing_reason}")
        value = None
        reason = ";".join(missing_reasons) or None
        if left_row is not None and right_row is not None and reason is None:
            assert left_row.value is not None
            assert right_row.value is not None
            value = left_row.value - right_row.value
        contrasts.append(
            BlockContrast(
                hypothesis_id=hypothesis_id,
                model_family=model_family,
                seed=seed,
                left_label=left_label,
                right_label=right_label,
                value=value,
                expected_direction=expected_direction,
                missing_reason=reason,
                source_trajectory_ids=source_ids or (f"missing:{model_family}:{seed}",),
            )
        )
    return tuple(contrasts)


def stratified_percentile_cluster_bootstrap(
    contrasts: Sequence[BlockContrast],
    *,
    replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    seed: int = ANALYSIS_SEED,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> ConfidenceInterval | None:
    """Resample seed blocks within each fixed model family and return a percentile CI."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one")
    _require_unique_contrast_blocks(contrasts)
    by_family: dict[str, list[float]] = defaultdict(list)
    for contrast in contrasts:
        if contrast.value is not None:
            by_family[contrast.model_family].append(contrast.value)
    if not by_family:
        return None
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(replicates):
        draw: list[float] = []
        for family in sorted(by_family):
            values = by_family[family]
            draw.extend(values[rng.randrange(len(values))] for _ in values)
        samples.append(statistics.fmean(draw))
    samples.sort()
    alpha = 1.0 - confidence_level
    return ConfidenceInterval(
        level=confidence_level,
        lower=_linear_percentile(samples, alpha / 2),
        upper=_linear_percentile(samples, 1 - alpha / 2),
        method="stratified_percentile_cluster_bootstrap",
        replicates=replicates,
        seed=seed,
    )


def paired_sign_flip_randomization(
    values: Sequence[float],
    *,
    exact_max_blocks: int = 20,
    monte_carlo_replicates: int = DEFAULT_RANDOMIZATION_REPLICATES,
    seed: int = ANALYSIS_SEED,
) -> RandomizationTest | None:
    """Two-sided paired sign-flip test, exact when feasible and deterministic otherwise."""

    if not values:
        return None
    if exact_max_blocks < 0 or monte_carlo_replicates < 1:
        raise ValueError("randomization limits must be non-negative and positive")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("randomization values must be finite")
    observed = abs(statistics.fmean(values))
    tolerance = 1e-15
    if len(values) <= exact_max_blocks:
        extreme = 0
        permutations = 1 << len(values)
        for signs in itertools.product((-1.0, 1.0), repeat=len(values)):
            permuted = abs(
                statistics.fmean(sign * value for sign, value in zip(signs, values, strict=True))
            )
            if permuted + tolerance >= observed:
                extreme += 1
        return RandomizationTest(
            p_value=extreme / permutations,
            method="exact_paired_sign_flip",
            permutations=permutations,
            seed=None,
        )
    rng = random.Random(seed)
    extreme = 0
    for _ in range(monte_carlo_replicates):
        permuted = abs(
            statistics.fmean(value if rng.getrandbits(1) else -value for value in values)
        )
        if permuted + tolerance >= observed:
            extreme += 1
    return RandomizationTest(
        p_value=(extreme + 1) / (monte_carlo_replicates + 1),
        method="monte_carlo_paired_sign_flip",
        permutations=monte_carlo_replicates,
        seed=seed,
    )


def hedges_g_z(values: Sequence[float]) -> tuple[float | None, str | None]:
    """Return paired Hedges g_z and an explicit undefined reason when needed."""

    if len(values) < 2:
        return None, "fewer_than_two_complete_blocks"
    standard_deviation = statistics.stdev(values)
    if standard_deviation == 0:
        return None, "zero_variance"
    correction = 1 - 3 / (4 * len(values) - 5)
    return correction * statistics.fmean(values) / standard_deviation, None


def analyze_block_contrasts(
    contrasts: Sequence[BlockContrast],
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    randomization_replicates: int = DEFAULT_RANDOMIZATION_REPLICATES,
    seed: int = ANALYSIS_SEED,
    exact_max_blocks: int = 20,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> ContrastAnalysis:
    """Summarize one hypothesis without discarding null or contradictory values."""

    if not contrasts:
        raise ValueError("at least one assigned block is required")
    hypothesis_ids = {row.hypothesis_id for row in contrasts}
    directions = {row.expected_direction for row in contrasts}
    if len(hypothesis_ids) != 1 or len(directions) != 1:
        raise ValueError("contrasts must belong to one hypothesis and direction")
    _require_unique_contrast_blocks(contrasts)
    valid_values = [row.value for row in contrasts if row.value is not None]
    values = [value for value in valid_values if value is not None]
    missing = [row for row in contrasts if row.value is None]
    missing_by_reason = dict(
        sorted(Counter(row.missing_reason or "unspecified" for row in missing).items())
    )
    by_family: dict[str, list[BlockContrast]] = defaultdict(list)
    for row in contrasts:
        by_family[row.model_family].append(row)
    strata = tuple(
        ModelFamilyStratum(
            model_family=family,
            mean=statistics.fmean(family_values) if family_values else None,
            valid_count=len(family_values),
            missing_count=len(rows) - len(family_values),
        )
        for family, rows in sorted(by_family.items())
        if (family_values := [row.value for row in rows if row.value is not None]) is not None
    )
    effect, effect_reason = hedges_g_z(values)
    mean = statistics.fmean(values) if values else None
    direction = next(iter(directions))
    return ContrastAnalysis(
        hypothesis_id=next(iter(hypothesis_ids)),
        mean_difference=mean,
        confidence_interval=stratified_percentile_cluster_bootstrap(
            contrasts,
            replicates=bootstrap_replicates,
            seed=seed,
            confidence_level=confidence_level,
        ),
        randomization_test=paired_sign_flip_randomization(
            values,
            exact_max_blocks=exact_max_blocks,
            monte_carlo_replicates=randomization_replicates,
            seed=seed,
        ),
        hedges_g_z=effect,
        hedges_g_z_undefined_reason=effect_reason,
        valid_block_count=len(values),
        assigned_block_count=len(contrasts),
        missing_block_count=len(missing),
        missing_by_reason=missing_by_reason,
        model_family_strata=strata,
        expected_direction=direction,
        direction_matches=(mean > 0 if direction == "positive" else mean < 0)
        if mean is not None
        else None,
    )


def holm_adjust(
    p_values: Mapping[str, float | None], *, alpha: float = 0.05
) -> tuple[MultiplicityResult, ...]:
    """Apply Holm step-down correction while retaining untestable family members."""

    if not p_values:
        raise ValueError("the confirmatory family cannot be empty")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    for value in p_values.values():
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError("p-values must be finite and between zero and one")
    family_size = len(p_values)
    valid = sorted(
        ((hypothesis_id, value) for hypothesis_id, value in p_values.items() if value is not None),
        key=lambda item: (item[1], item[0]),
    )
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (hypothesis_id, value) in enumerate(valid):
        candidate = min(1.0, (family_size - rank) * value)
        running_max = max(running_max, candidate)
        adjusted[hypothesis_id] = running_max
    return tuple(
        MultiplicityResult(
            hypothesis_id=hypothesis_id,
            raw_p_value=p_values[hypothesis_id],
            holm_adjusted_p_value=adjusted.get(hypothesis_id),
            reject_at_alpha=adjusted.get(hypothesis_id, 1.0) < alpha,
            family_size=family_size,
        )
        for hypothesis_id in sorted(p_values)
    )


def summarize_recovery(
    observations: Iterable[RecoveryObservation], *, horizon: int = 15
) -> RecoverySummary:
    """Build a discrete Kaplan-Meier-style unrecovered curve and restricted mean."""

    if not 1 <= horizon <= 15:
        raise ValueError("horizon must be in [1, 15]")
    rows = tuple(observations)
    valid = [row for row in rows if row.time is not None]
    missing = [row for row in rows if row.time is None]
    missing_by_reason = dict(
        sorted(Counter(row.missing_reason or "unspecified" for row in missing).items())
    )
    if not valid:
        return RecoverySummary(
            restricted_mean_time=None,
            horizon=horizon,
            assigned_count=len(rows),
            valid_count=0,
            missing_count=len(missing),
            missing_by_reason=missing_by_reason,
            risk_curve=(),
        )
    survival = 1.0
    points = [
        RecoveryRiskPoint(
            time=0,
            at_risk=len(valid),
            recovered_events=0,
            censored=0,
            unrecovered_probability=1.0,
        )
    ]
    restricted_mean = 0.0
    for time in range(1, horizon + 1):
        # Discrete RMST is sum of S(t-1) over t=1...horizon.
        restricted_mean += survival
        at_risk = sum(1 for row in valid if row.time is not None and row.time >= time)
        events = sum(1 for row in valid if row.time == time and row.recovered)
        censored = sum(1 for row in valid if row.time == time and row.recovered is False)
        if at_risk:
            survival *= 1 - events / at_risk
        points.append(
            RecoveryRiskPoint(
                time=time,
                at_risk=at_risk,
                recovered_events=events,
                censored=censored,
                unrecovered_probability=survival,
            )
        )
    return RecoverySummary(
        restricted_mean_time=restricted_mean,
        horizon=horizon,
        assigned_count=len(rows),
        valid_count=len(valid),
        missing_count=len(missing),
        missing_by_reason=missing_by_reason,
        risk_curve=tuple(points),
    )


def paired_restricted_mean_difference(
    left: RecoverySummary, right: RecoverySummary
) -> float | None:
    """Subtract right-arm RMST from left-arm RMST without imputing missing summaries."""

    if left.horizon != right.horizon:
        raise ValueError("recovery summaries must use the same horizon")
    if left.restricted_mean_time is None or right.restricted_mean_time is None:
        return None
    return left.restricted_mean_time - right.restricted_mean_time


def sensitivity_scaffold() -> tuple[SensitivityResult, ...]:
    """Return all prespecified sensitivities as explicit not-run records."""

    return tuple(
        SensitivityResult(
            specification=specification,
            note="Prespecified sensitivity has not been executed; no estimate is implied.",
        )
        for specification in PRESPECIFIED_SENSITIVITIES
    )


def _index_reductions(
    reductions: Iterable[TrajectoryReduction], side: str
) -> dict[tuple[str, int], TrajectoryReduction]:
    indexed: dict[tuple[str, int], TrajectoryReduction] = {}
    for row in reductions:
        key = (row.model_family, row.seed)
        if key in indexed:
            raise ValueError(f"duplicate {side} trajectory summary for block {key!r}")
        indexed[key] = row
    return indexed


def _require_unique_contrast_blocks(contrasts: Sequence[BlockContrast]) -> None:
    keys = [(row.model_family, row.seed) for row in contrasts]
    if len(set(keys)) != len(keys):
        raise ValueError("each model-family/seed block may contribute at most one contrast")


def _linear_percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])
