from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import affective_belief_persistence.harness as harness
from affective_belief_persistence.harness.config import (
    Gate2HarnessConfig,
    HarnessConfigError,
    LoadedHarnessConfig,
    load_harness_config,
)
from affective_belief_persistence.harness.contracts import (
    HarnessCheckpoint,
    HarnessStepEvidence,
    SelectedMemoryEvidence,
)
from affective_belief_persistence.harness.model import HarnessModelError, ModelLedgerState
from affective_belief_persistence.harness.runner import (
    CompositeCheckpointBundle,
    CompositeCheckpointError,
    HarnessError,
    _artifact_payload,
    capture_composite_checkpoint,
    restore_composite_checkpoint,
    start_cell,
)


def test_lazy_harness_exports_are_import_cycle_safe() -> None:
    exported = dir(harness)
    assert exported == sorted(exported)
    for name in harness.__all__:
        assert getattr(harness, name) is not None
    missing_name = "missing"
    with pytest.raises(AttributeError, match=missing_name):
        getattr(harness, missing_name)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.update(
                intervention_configs=dict(reversed(payload["intervention_configs"].items()))
            ),
            "intervention order",
        ),
        (
            lambda payload: payload["consumed_artifacts"][0].update(artifact_id="wrong"),
            "Issues 9 through 12",
        ),
        (
            lambda payload: payload["instruction"].update(
                active_for_formations=["romantic_prompt", "romantic_prompt"]
            ),
            "must be unique",
        ),
        (
            lambda payload: payload.update(base_scenario_path="/absolute/scenario.yaml"),
            "repository-relative",
        ),
    ],
)
def test_config_rejects_each_frozen_boundary(
    gate2_config: LoadedHarnessConfig,
    mutate,
    message: str,
) -> None:
    payload = gate2_config.config.model_dump(mode="json")
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        Gate2HarnessConfig.model_validate(payload)


def test_config_wraps_malformed_yaml(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs/harness"
    config_dir.mkdir(parents=True)
    path = config_dir / "broken.yaml"
    path.write_text("formation_conditions: [", encoding="utf-8")
    with pytest.raises(HarnessConfigError, match="invalid Gate 2 harness config"):
        load_harness_config(path, project_root=tmp_path)


def test_selected_memory_rejects_partial_interpretation_and_duplicate_sources() -> None:
    common = {
        "memory_id": "memory-1",
        "summary": "Synthetic summary.",
        "observable_facts": ("Synthetic fact.",),
        "source_ids": ("event-1", "fact-1"),
    }
    with pytest.raises(ValidationError, match="all present or all absent"):
        SelectedMemoryEvidence.create(
            **common,
            active_interpretation="An interpretation.",
            active_interpretation_id=None,
            active_interpretation_revision=None,
        )
    with pytest.raises(ValidationError, match="source IDs must be unique"):
        SelectedMemoryEvidence.create(
            **{**common, "source_ids": ("event-1", "event-1")},
            active_interpretation=None,
            active_interpretation_id=None,
            active_interpretation_revision=None,
        )


@pytest.fixture
def checkpointed_cell(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
):
    cell = start_cell(
        formation="memory_plus_investment",
        intervention="memory_reframing",
        loaded=gate2_config,
        project_root=project_root,
    )
    cell.run_through(30)
    return cell


@pytest.mark.parametrize(
    ("day_index", "updates", "message"),
    [
        (0, {"step_index": 1}, "day, index, and phase"),
        (0, {"held_out_shock_confirmed": True}, "exactly on day 26"),
        (25, {"event_provenance_source_ids": ("wrong-source",)}, "held-out provenance"),
        (0, {"intervention_activated_this_step": True}, "exactly on day 30"),
        (0, {"intervention_record_sha256": "a" * 64}, "post-day-30 evidence"),
        (0, {"intervention_target_ids": ("memory-1",)}, "activation step"),
        (0, {"resource_spent": 1, "resource_remaining": 8}, "not conserved"),
        (
            0,
            {
                "execution_order": (
                    "pre_action_overlay",
                    "memory_retrieval",
                    "model_input",
                    "action_commitment",
                    "resource_debit",
                    "consequence_application",
                    "public_language",
                    "memory_commit",
                )
            },
            "memory_retrieval",
        ),
        (0, {"evidence_sha256": "0" * 64}, "evidence hash mismatch"),
    ],
)
def test_step_evidence_rejects_corrupt_invariants(
    checkpointed_cell,
    day_index: int,
    updates: dict[str, object],
    message: str,
) -> None:
    payload = checkpointed_cell.evidence[day_index].model_dump(mode="json")
    payload.update(updates)
    with pytest.raises(ValidationError, match=message):
        HarnessStepEvidence.model_validate(payload)


def test_step_evidence_rejects_duplicate_selected_memory(checkpointed_cell) -> None:
    evidence = next(item for item in checkpointed_cell.evidence if item.selected_memories)
    payload = evidence.model_dump(mode="json")
    payload["selected_memories"] = [payload["selected_memories"][0]] * 2
    with pytest.raises(ValidationError, match="must be unique"):
        HarnessStepEvidence.model_validate(payload)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"evidence_count": 28}, "does not end before next_day"),
        ({"checkpoint_sequence": 28}, "sequence must equal committed steps"),
        ({"checkpoint_sha256": "0" * 64}, "checkpoint hash mismatch"),
    ],
)
def test_checkpoint_contract_rejects_torn_pointer(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
    updates: dict[str, object],
    message: str,
) -> None:
    cell = start_cell(
        formation="neutral_connection",
        intervention="none",
        loaded=gate2_config,
        project_root=project_root,
    )
    cell.run_through(29)
    payload = capture_composite_checkpoint(cell).pointer.model_dump(mode="json")
    payload.update(updates)
    with pytest.raises(ValidationError, match=message):
        HarnessCheckpoint.model_validate(payload)


def test_empty_and_backwards_checkpoint_operations_fail_closed(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    cell = start_cell(
        formation="neutral_connection",
        intervention="none",
        loaded=gate2_config,
        project_root=project_root,
    )
    with pytest.raises(CompositeCheckpointError, match="nonempty aligned"):
        capture_composite_checkpoint(cell)
    cell.run_through(2)
    with pytest.raises(HarnessError, match="precedes the current"):
        cell.run_through(1)


def test_discontinuous_checkpoint_evidence_fails_closed(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    cell = start_cell(
        formation="neutral_connection",
        intervention="none",
        loaded=gate2_config,
        project_root=project_root,
    )
    cell.run_through(2)
    bundle = capture_composite_checkpoint(cell)
    broken_second = bundle.evidence[1].model_copy(update={"previous_evidence_sha256": "0" * 64})
    corrupt = CompositeCheckpointBundle(
        pointer=bundle.pointer,
        simulation=bundle.simulation,
        intervention=bundle.intervention,
        evidence=(bundle.evidence[0], broken_second),
    )
    with pytest.raises(CompositeCheckpointError, match="swapped or discontinuous"):
        restore_composite_checkpoint(
            corrupt,
            formation="neutral_connection",
            intervention="none",
            loaded=gate2_config,
            project_root=project_root,
        )


def test_model_ledger_and_trace_guards_fail_closed(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    cell = start_cell(
        formation="neutral_connection",
        intervention="none",
        loaded=gate2_config,
        project_root=project_root,
    )
    with pytest.raises(HarnessModelError, match="missing or duplicated"):
        cell.model.trace_for_request("missing-request")
    with pytest.raises(HarnessModelError, match="future model ledger"):
        cell.model.restore_state(ModelLedgerState(ledger_sha256="a" * 64, trace_count=1))


def test_artifact_parser_rejects_every_unaccepted_shape(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(HarnessError, match="regular file"):
        _artifact_payload(missing, "expected")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(HarnessError, match="invalid consumed artifact"):
        _artifact_payload(invalid, "expected")

    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(HarnessError, match="not a JSON object"):
        _artifact_payload(array, "expected")

    rejected = tmp_path / "rejected.json"
    rejected.write_text(
        json.dumps({"artifact_id": "expected", "status": "rejected"}),
        encoding="utf-8",
    )
    with pytest.raises(HarnessError, match="not accepted"):
        _artifact_payload(rejected, "expected")
