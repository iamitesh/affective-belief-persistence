"""Renderer-independent table and plot data contracts for Issue #14.

These specifications contain operational values and provenance only.  A later
reporting layer may render them, but must not infer missing values or replace the
frozen terminology embedded here.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .analysis import (
    AnalysisModel,
    AnalysisProvenance,
    ContrastAnalysis,
    RecoverySummary,
    deterministic_sha256,
)

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Scalar = bool | float | int | str | None


class TableColumnSpec(AnalysisModel):
    column_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value_type: Literal["boolean", "count", "number", "text"]
    unit: str | None = Field(default=None, min_length=1)
    nullable: bool = False


class TableDataSpec(AnalysisModel):
    table_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    operational_note: str = Field(min_length=1)
    columns: tuple[TableColumnSpec, ...] = Field(min_length=1)
    rows: tuple[dict[str, Scalar], ...]
    provenance: AnalysisProvenance
    data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_shape_and_hash(self) -> TableDataSpec:
        column_ids = tuple(column.column_id for column in self.columns)
        if len(set(column_ids)) != len(column_ids):
            raise ValueError("table column IDs must be unique")
        expected_keys = set(column_ids)
        for row in self.rows:
            if set(row) != expected_keys:
                raise ValueError("each table row must have exactly the declared columns")
            for column in self.columns:
                value = row[column.column_id]
                if value is None and not column.nullable:
                    raise ValueError(f"non-nullable table column {column.column_id!r} is null")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("table values must be finite")
        payload = {
            "table_id": self.table_id,
            "columns": [column.model_dump(mode="json") for column in self.columns],
            "rows": list(self.rows),
        }
        if deterministic_sha256(payload) != self.data_sha256:
            raise ValueError("table data_sha256 does not match the canonical payload")
        return self


class PlotSeriesSpec(AnalysisModel):
    series_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    x: tuple[FiniteFloat, ...]
    y: tuple[FiniteFloat | None, ...]
    lower: tuple[FiniteFloat | None, ...] | None = None
    upper: tuple[FiniteFloat | None, ...] | None = None
    at_risk: tuple[int, ...] | None = None
    missing_count: tuple[int, ...] | None = None

    @model_validator(mode="after")
    def validate_lengths_and_bands(self) -> PlotSeriesSpec:
        length = len(self.x)
        if len(self.y) != length:
            raise ValueError("plot x and y lengths must match")
        for optional_values in (self.lower, self.upper, self.at_risk, self.missing_count):
            if optional_values is not None and len(optional_values) != length:
                raise ValueError("all plot series fields must match x length")
        if (self.lower is None) != (self.upper is None):
            raise ValueError("plot uncertainty bands require both lower and upper")
        if self.lower is not None and self.upper is not None:
            for lower, value, upper in zip(self.lower, self.y, self.upper, strict=True):
                if lower is not None and upper is not None and lower > upper:
                    raise ValueError("plot lower band exceeds upper band")
                if value is not None and lower is not None and value < lower:
                    raise ValueError("plot value falls below its lower band")
                if value is not None and upper is not None and value > upper:
                    raise ValueError("plot value exceeds its upper band")
        return self


class PlotDataSpec(AnalysisModel):
    plot_id: str = Field(min_length=1)
    plot_type: Literal["daily_curve", "forest", "missingness", "recovery_curve"]
    title: str = Field(min_length=1)
    x_label: str = Field(min_length=1)
    y_label: str = Field(min_length=1)
    y_unit: str = Field(min_length=1)
    operational_note: str = Field(min_length=1)
    series: tuple[PlotSeriesSpec, ...] = Field(min_length=1)
    provenance: AnalysisProvenance
    data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_series_and_hash(self) -> PlotDataSpec:
        series_ids = tuple(series.series_id for series in self.series)
        if len(set(series_ids)) != len(series_ids):
            raise ValueError("plot series IDs must be unique")
        payload = {
            "plot_id": self.plot_id,
            "plot_type": self.plot_type,
            "series": [series.model_dump(mode="json") for series in self.series],
        }
        if deterministic_sha256(payload) != self.data_sha256:
            raise ValueError("plot data_sha256 does not match the canonical payload")
        return self


def build_contrast_table(
    analyses: tuple[ContrastAnalysis, ...],
    *,
    provenance: AnalysisProvenance,
    table_id: str = "confirmatory-contrast-summary",
) -> TableDataSpec:
    """Build an explicit-null H1-H6 summary table without claim interpretation."""

    columns = (
        TableColumnSpec(column_id="hypothesis_id", label="Hypothesis", value_type="text"),
        TableColumnSpec(
            column_id="mean_difference",
            label="Mean paired difference",
            value_type="number",
            unit="raw metric units",
            nullable=True,
        ),
        TableColumnSpec(
            column_id="ci_lower",
            label="95% CI lower",
            value_type="number",
            unit="raw metric units",
            nullable=True,
        ),
        TableColumnSpec(
            column_id="ci_upper",
            label="95% CI upper",
            value_type="number",
            unit="raw metric units",
            nullable=True,
        ),
        TableColumnSpec(
            column_id="raw_p_value", label="Raw p-value", value_type="number", nullable=True
        ),
        TableColumnSpec(
            column_id="hedges_g_z", label="Hedges g_z", value_type="number", nullable=True
        ),
        TableColumnSpec(column_id="valid_blocks", label="Complete blocks", value_type="count"),
        TableColumnSpec(column_id="missing_blocks", label="Missing blocks", value_type="count"),
        TableColumnSpec(
            column_id="direction_matches",
            label="Frozen direction matched",
            value_type="boolean",
            nullable=True,
        ),
    )
    rows: tuple[dict[str, Scalar], ...] = tuple(
        {
            "hypothesis_id": analysis.hypothesis_id,
            "mean_difference": analysis.mean_difference,
            "ci_lower": analysis.confidence_interval.lower
            if analysis.confidence_interval is not None
            else None,
            "ci_upper": analysis.confidence_interval.upper
            if analysis.confidence_interval is not None
            else None,
            "raw_p_value": analysis.randomization_test.p_value
            if analysis.randomization_test is not None
            else None,
            "hedges_g_z": analysis.hedges_g_z,
            "valid_blocks": analysis.valid_block_count,
            "missing_blocks": analysis.missing_block_count,
            "direction_matches": analysis.direction_matches,
        }
        for analysis in sorted(analyses, key=lambda item: item.hypothesis_id)
    )
    payload = {
        "table_id": table_id,
        "columns": [column.model_dump(mode="json") for column in columns],
        "rows": list(rows),
    }
    return TableDataSpec(
        table_id=table_id,
        title="Frozen paired-contrast analysis",
        operational_note=(
            "Values describe observable synthetic-agent metrics in raw units; null, missing, "
            "and opposite-direction estimates are retained and imply no subjective state."
        ),
        columns=columns,
        rows=rows,
        provenance=provenance,
        data_sha256=deterministic_sha256(payload),
    )


def build_recovery_plot(
    summary: RecoverySummary,
    *,
    provenance: AnalysisProvenance,
    plot_id: str,
    series_id: str,
    series_label: str,
) -> PlotDataSpec:
    """Build renderer-neutral unrecovered probability and risk-set data."""

    if not summary.risk_curve:
        raise ValueError("a recovery plot requires at least one valid recovery observation")
    series = PlotSeriesSpec(
        series_id=series_id,
        label=series_label,
        x=tuple(float(point.time) for point in summary.risk_curve),
        y=tuple(point.unrecovered_probability for point in summary.risk_curve),
        at_risk=tuple(point.at_risk for point in summary.risk_curve),
        missing_count=tuple(summary.missing_count for _ in summary.risk_curve),
    )
    payload = {
        "plot_id": plot_id,
        "plot_type": "recovery_curve",
        "series": [series.model_dump(mode="json")],
    }
    return PlotDataSpec(
        plot_id=plot_id,
        plot_type="recovery_curve",
        title="Unrecovered paired excess partner allocation",
        x_label="Days after reality shock",
        y_label="Unrecovered probability",
        y_unit="proportion",
        operational_note=(
            "Recovery is the frozen two-consecutive-day paired allocation threshold; "
            "right-censored trajectories remain in the risk set until censoring."
        ),
        series=(series,),
        provenance=provenance,
        data_sha256=deterministic_sha256(payload),
    )
