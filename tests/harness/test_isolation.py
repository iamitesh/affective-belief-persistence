from __future__ import annotations

import json
from pathlib import Path

from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.harness.config import LoadedHarnessConfig
from affective_belief_persistence.harness.contracts import INTERVENTION_CONDITIONS
from affective_belief_persistence.harness.runner import run_cell, run_gate2_matrix, start_cell
from affective_belief_persistence.interventions.audit import audit_record


def pre_day29_signature(cell) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.simulation_record_sha256,
            item.model_input_sha256,
            item.action_prompt_sha256,
            item.action_cache_key,
            item.public_language_prompt_sha256,
            item.public_language_cache_key,
            item.memory_checkpoint_sha256,
            item.model_ledger_sha256,
        )
        for item in cell.evidence[:29]
    )


def test_intervention_assignment_cannot_change_days_one_through_twenty_nine(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    arms = []
    for intervention in INTERVENTION_CONDITIONS:
        cell = start_cell(
            formation="memory_plus_investment",
            intervention=intervention,
            loaded=gate2_config,
            project_root=project_root,
        )
        cell.run_through(29)
        arms.append(cell)
    reference = pre_day29_signature(arms[0])
    assert all(pre_day29_signature(cell) == reference for cell in arms[1:])
    assert all(cell.runtime.records == () for cell in arms)


def test_day30_each_condition_changes_only_its_declared_layer(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    cells = {
        "none": run_cell(
            "memory_plus_investment",
            "none",
            loaded=gate2_config,
            project_root=project_root,
        ),
        "instruction_removal": run_cell(
            "romantic_prompt",
            "instruction_removal",
            loaded=gate2_config,
            project_root=project_root,
        ),
        "memory_blocking": run_cell(
            "memory_plus_investment",
            "memory_blocking",
            loaded=gate2_config,
            project_root=project_root,
        ),
        "memory_reframing": run_cell(
            "memory_plus_investment",
            "memory_reframing",
            loaded=gate2_config,
            project_root=project_root,
        ),
    }
    expected = {
        "none": (),
        "instruction_removal": ("instructions",),
        "memory_blocking": ("retrieval_policy",),
        "memory_reframing": ("interpretations",),
    }
    for condition, cell in cells.items():
        record = cell.runtime.records[0]
        audit = audit_record(record)
        assert record.changed_layers == expected[condition]
        assert audit.passed
        assert record.activation_day == 30
        assert record.shock_validation.held_out_provenance_confirmed is True
        if condition in {"memory_blocking", "memory_reframing"}:
            assert all(
                cell.runtime.memory.store.get(target).simulation_day <= 25
                for target in record.target_ids
            )
    none_record = cells["none"].runtime.records[0]
    assert none_record.before == none_record.after
    blocking = cells["memory_blocking"].runtime.records[0]
    assert blocking.before.memory_storage_sha256 == blocking.after.memory_storage_sha256
    reframing = cells["memory_reframing"].runtime.records[0]
    assert reframing.before.observable_facts_sha256 == reframing.after.observable_facts_sha256
    assert reframing.before.source_event_ids_sha256 == reframing.after.source_event_ids_sha256


def test_exact_full_gate2_matrix_is_mock_engineering_evidence(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    manifest = run_gate2_matrix(
        gate2_config,
        project_root=project_root,
        failure_injections_passed=(
            "swapped_checkpoint",
            "corrupt_component",
            "day30_failure_rollback",
            "invalid_action_rollback",
            "cache_miss_rejected",
        ),
    )
    assert len(manifest.cells) == 16
    assert manifest.record_count == manifest.evidence_count == 640
    assert manifest.live_calls == 0
    assert manifest.scientific_results is False
    assert manifest.replay_matches is True
    assert manifest.interventions_are_isolated is True
    assert {
        (cell.cell.formation_condition, cell.cell.intervention_condition) for cell in manifest.cells
    } == {
        (formation, intervention)
        for formation in manifest.formation_conditions
        for intervention in manifest.intervention_conditions
    }
    artifact = json.loads(
        (project_root / "artifacts/orchestration/gate-2.json").read_text(encoding="utf-8")
    )
    assert artifact["run"]["run_id"] == manifest.run_id
    assert artifact["run"]["manifest_sha256"] == manifest.manifest_sha256
    assert artifact["run"]["cell_evidence_heads"] == [
        {
            "formation": cell.cell.formation_condition,
            "intervention": cell.cell.intervention_condition,
            "cell_id": cell.cell.cell_id,
            "evidence_sha256": cell.evidence_chain_sha256,
        }
        for cell in manifest.cells
    ]
    assert artifact["consumed_artifacts"] == [
        {
            "artifact_id": item.artifact_id,
            "path": item.path,
            "sha256": sha256_file(project_root / item.path),
        }
        for item in manifest.consumed_artifacts
    ]
