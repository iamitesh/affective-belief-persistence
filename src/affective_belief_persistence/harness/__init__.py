"""Lazy Gate 2 API; schema registration may import contracts without cycles."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "HARNESS_SCHEMA_MODELS": ("contracts", "HARNESS_SCHEMA_MODELS"),
    "CompositeCheckpointBundle": ("runner", "CompositeCheckpointBundle"),
    "CompositeCheckpointError": ("runner", "CompositeCheckpointError"),
    "Gate2HarnessConfig": ("config", "Gate2HarnessConfig"),
    "HarnessCellIdentity": ("contracts", "HarnessCellIdentity"),
    "HarnessCheckpoint": ("contracts", "HarnessCheckpoint"),
    "HarnessRunManifest": ("contracts", "HarnessRunManifest"),
    "HarnessStepEvidence": ("contracts", "HarnessStepEvidence"),
    "capture_composite_checkpoint": ("runner", "capture_composite_checkpoint"),
    "load_harness_config": ("config", "load_harness_config"),
    "restore_composite_checkpoint": ("runner", "restore_composite_checkpoint"),
    "run_cell": ("runner", "run_cell"),
    "run_cell_resumed": ("runner", "run_cell_resumed"),
    "run_gate2_matrix": ("runner", "run_gate2_matrix"),
    "start_cell": ("runner", "start_cell"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(
        import_module(f"affective_belief_persistence.harness.{module_name}"),
        attribute,
    )
    globals()[name] = value
    return value
