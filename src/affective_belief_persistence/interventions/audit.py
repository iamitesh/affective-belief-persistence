"""Deterministic leakage and intervention-layer audit helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from affective_belief_persistence.data.generation import build_dataset
from affective_belief_persistence.data.validation import LeakageFinding, scan_formation_leakage
from affective_belief_persistence.safety import SafetyEvaluator, load_safety_policy

from .contracts import InterventionRecord


@dataclass(frozen=True)
class IsolationAudit:
    condition: str
    changed_layers: tuple[str, ...]
    protected_layers_unchanged: bool
    facts_preserved: bool
    source_events_preserved: bool
    storage_preserved: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.protected_layers_unchanged,
                self.facts_preserved,
                self.source_events_preserved,
                self.storage_preserved,
            )
        )


def audit_record(record: InterventionRecord) -> IsolationAudit:
    before, after = record.before, record.after
    protected = (
        before.observable_facts_sha256 == after.observable_facts_sha256
        and before.source_event_ids_sha256 == after.source_event_ids_sha256
        and before.belief_ledger_sha256 == after.belief_ledger_sha256
    )
    return IsolationAudit(
        condition=record.intervention_condition,
        changed_layers=record.changed_layers,
        protected_layers_unchanged=protected,
        facts_preserved=before.observable_facts_sha256 == after.observable_facts_sha256,
        source_events_preserved=(before.source_event_ids_sha256 == after.source_event_ids_sha256),
        storage_preserved=before.memory_storage_sha256 == after.memory_storage_sha256,
    )


def scan_training_leakage(project_root: Path) -> tuple[LeakageFinding, ...]:
    """Scan only formation/training-eligible records using the frozen policy."""

    build = build_dataset(project_root)
    formation = tuple(
        event
        for path, events in build.partitions.items()
        if path.startswith("data/formation/")
        for event in events
    )
    evaluator = SafetyEvaluator(load_safety_policy(project_root / "configs/safety-policy.yaml"))
    return scan_formation_leakage(formation, evaluator)
