"""Lazy public API for the held-out shock and intervention engine."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "INTERVENTION_SCHEMA_MODELS": ("contracts", "INTERVENTION_SCHEMA_MODELS"),
    "InstructionDirective": ("contracts", "InstructionDirective"),
    "InterventionCheckpoint": ("runtime", "InterventionCheckpoint"),
    "InterventionCondition": ("contracts", "InterventionCondition"),
    "InterventionError": ("runtime", "InterventionError"),
    "InterventionRecord": ("contracts", "InterventionRecord"),
    "InterventionRuntime": ("runtime", "InterventionRuntime"),
    "InterventionSpec": ("contracts", "InterventionSpec"),
    "IsolationAudit": ("audit", "IsolationAudit"),
    "LayerSnapshot": ("contracts", "LayerSnapshot"),
    "PreActionOverlay": ("contracts", "PreActionOverlay"),
    "RealityShockValidation": ("contracts", "RealityShockValidation"),
    "SimulationCheckpointBinding": ("runtime", "SimulationCheckpointBinding"),
    "audit_record": ("audit", "audit_record"),
    "load_intervention_spec": ("runtime", "load_intervention_spec"),
    "scan_training_leakage": ("audit", "scan_training_leakage"),
    "validate_reality_shock": ("runtime", "validate_reality_shock"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(
        import_module(f"affective_belief_persistence.interventions.{module_name}"),
        attribute,
    )
    globals()[name] = value
    return value
