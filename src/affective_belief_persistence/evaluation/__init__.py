"""Lazy public boundary for the Issue #14 evaluation engine."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "ActionDecision": ".contracts",
    "AnalysisProvenance": ".analysis",
    "BlockContrast": ".analysis",
    "CoherentAdaptationDay": ".contracts",
    "ContrastAnalysis": ".analysis",
    "DailyFactOutcome": ".contracts",
    "DailyMetricObservation": ".analysis",
    "DailyPairedAllocation": ".contracts",
    "EVALUATION_SCHEMA_MODELS": ".contracts",
    "ExperimentAssignment": ".matrix",
    "ExperimentMatrix": ".matrix",
    "ExperimentResult": ".contracts",
    "FactProbe": ".contracts",
    "FuturePlanSelection": ".contracts",
    "HardBudgetAccount": ".runner",
    "ImmutableRawResultStore": ".runner",
    "InterpretationProbe": ".contracts",
    "LanguageActionPair": ".contracts",
    "LanguageObservation": ".contracts",
    "LoadedEvaluationConfig": ".config",
    "MetricId": ".contracts",
    "MetricRecord": ".contracts",
    "MissingReason": ".contracts",
    "MultiplicityResult": ".analysis",
    "OfflineEvaluationConfig": ".config",
    "OfflineEvaluationRunner": ".runner",
    "OfflineExecutionOutcome": ".runner",
    "PlotDataSpec": ".plots",
    "RecoveryObservation": ".analysis",
    "RecoverySummary": ".analysis",
    "ResultStatus": ".runner",
    "RetrievalDecision": ".contracts",
    "TableDataSpec": ".plots",
    "TrajectoryReduction": ".analysis",
    "TrajectoryResult": ".runner",
    "analyze_block_contrasts": ".analysis",
    "build_contrast_table": ".plots",
    "build_recovery_plot": ".plots",
    "coherent_adaptation_rate": ".metrics",
    "expand_experiment_matrix": ".matrix",
    "fact_correction_accuracy": ".metrics",
    "fact_error_auc": ".metrics",
    "form_paired_block_contrasts": ".analysis",
    "future_plan_contamination_rate": ".metrics",
    "h1_language_action_effect_gap": ".metrics",
    "h2_action_persistence_auc": ".metrics",
    "h3_excess_action_persistence_auc": ".metrics",
    "h4_instruction_selectivity_index": ".metrics",
    "h5_coherent_adaptation_rate": ".metrics",
    "h6_correction_resistance_gap": ".metrics",
    "hedges_g_z": ".analysis",
    "holm_adjust": ".analysis",
    "interpretation_support_rate": ".metrics",
    "language_action_contradiction_rate": ".metrics",
    "load_evaluation_config": ".config",
    "metric_definition": ".registry",
    "normalized_opportunity_cost": ".metrics",
    "paired_restricted_mean_difference": ".analysis",
    "paired_sign_flip_randomization": ".analysis",
    "partner_allocation_rate": ".metrics",
    "partner_choice_rate": ".metrics",
    "positive_excess_action_auc": ".metrics",
    "recovery_curve": ".metrics",
    "recovery_time": ".metrics",
    "reduce_trajectory_observations": ".analysis",
    "relationship_language_rate": ".metrics",
    "relationship_memory_intrusion_rate": ".metrics",
    "sensitivity_scaffold": ".analysis",
    "stratified_percentile_cluster_bootstrap": ".analysis",
    "summarize_recovery": ".analysis",
    "unrelated_decision_bias_rate": ".metrics",
}

__all__ = tuple(sorted(_EXPORTS))


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
