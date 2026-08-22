from __future__ import annotations

from pathlib import Path

import pytest

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.interventions import (
    InstructionDirective,
    InterventionCheckpoint,
    InterventionError,
    InterventionRecord,
    InterventionRuntime,
    audit_record,
)
from affective_belief_persistence.models.contracts import (
    ActionContext,
    ModelInput,
    Phase,
    ResourceContext,
)
from affective_belief_persistence.simulation.engine import SimulationEngine
from affective_belief_persistence.simulation.model import DeterministicTwoStageMockModel
from affective_belief_persistence.simulation.scenario_loader import load_scenario

from .conftest import build_runtime


class FailDay30Language:
    def __init__(self, wrapped: DeterministicTwoStageMockModel) -> None:
        self.wrapped = wrapped
        self.model_id = wrapped.model_id
        self.revision = wrapped.revision

    def select_action(self, request, *, seed: int):
        return self.wrapped.select_action(request, seed=seed)

    def generate_public_language(
        self,
        request,
        selection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        if request.day == 30:
            raise RuntimeError("synthetic day-30 language failure")
        return self.wrapped.generate_public_language(
            request,
            selection,
            action_commitment_sha256=action_commitment_sha256,
            seed=seed,
        )


def run_condition(
    project_root: Path,
    config_name: str,
    instruction: InstructionDirective,
    *,
    max_steps: int = 40,
) -> tuple[SimulationEngine, InterventionRuntime]:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    runtime = build_runtime(project_root, config_name, instruction)
    engine = SimulationEngine(
        scenario,
        DeterministicTwoStageMockModel(scenario.model_settings),
        memory=runtime,
    )
    engine.run(max_steps=max_steps)
    return engine, runtime


def test_offline_four_treatment_matrix_completes_with_one_day30_record(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    configs = ("none", "instruction-removal", "memory-blocking", "memory-reframing")
    results = {
        name: run_condition(project_root, name, relationship_instruction) for name in configs
    }

    assert all(engine.state.completed for engine, _ in results.values())
    assert all(len(runtime.records) == 1 for _, runtime in results.values())
    assert all(runtime.records[0].activation_day == 30 for _, runtime in results.values())
    assert all(runtime.shock_validation is not None for _, runtime in results.values())
    assert all(audit_record(runtime.records[0]).passed for _, runtime in results.values())
    assert {runtime.records[0].intervention_condition for _, runtime in results.values()} == {
        "none",
        "instruction_removal",
        "memory_blocking",
        "memory_reframing",
    }


def test_no_treatment_has_zero_hidden_mutation(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    _, runtime = run_condition(project_root, "none", relationship_instruction)
    record = runtime.records[0]

    assert record.no_op_reason == "assigned_no_treatment"
    assert record.changed_layers == ()
    assert record.before == record.after


def test_instruction_removal_changes_prompt_visible_instruction_layer_only(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    _, runtime = run_condition(
        project_root,
        "instruction-removal",
        relationship_instruction,
        max_steps=30,
    )
    record = runtime.records[0]
    base_input = ModelInput(
        run_id="1" * 64,
        request_id="request-30",
        event_id="adaptation-30-memory_plus_investment",
        day=30,
        phase=Phase.ADAPTATION,
        observable_facts=("A synthetic fact.",),
        resources=ResourceContext(available=10),
        allowed_actions=(ActionContext(action_id="take-rest", description="Rest", cost=3),),
        prompt_version="decision-v1",
    )
    enriched = runtime.overlay_model_input(base_input)

    assert record.changed_layers == ("instructions",)
    assert record.target_ids == ("relationship-framing-v1",)
    assert record.before.memory_storage_sha256 == record.after.memory_storage_sha256
    assert runtime.active_instruction_ids == ()
    assert enriched.run_id != base_input.run_id
    assert enriched.active_intervention is not None
    assert enriched.active_intervention.intervention_type == "instruction_state"
    assert enriched.active_intervention.parameters["active_instruction_text"] == ""
    assert "instruction_removal" not in str(enriched.active_intervention)
    assert record.record_sha256 not in str(enriched.active_intervention)


def test_non_instruction_assignments_are_not_disclosed_in_model_overlay(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    base_input = ModelInput(
        run_id="2" * 64,
        request_id="request-30",
        event_id="adaptation-30-memory_plus_investment",
        day=30,
        phase=Phase.ADAPTATION,
        observable_facts=("A synthetic fact.",),
        resources=ResourceContext(available=10),
        allowed_actions=(ActionContext(action_id="take-rest", description="Rest", cost=3),),
        prompt_version="decision-v1",
    )
    overlays = []
    run_ids = []
    for name in ("none", "memory-blocking", "memory-reframing"):
        _, runtime = run_condition(
            project_root,
            name,
            relationship_instruction,
            max_steps=30,
        )
        enriched = runtime.overlay_model_input(base_input)
        overlays.append(enriched.active_intervention)
        run_ids.append(enriched.run_id)
        assert runtime.records[0].intervention_condition not in str(enriched.active_intervention)
        assert runtime.records[0].record_sha256 not in str(enriched.active_intervention)

    assert overlays[0] == overlays[1] == overlays[2]
    assert run_ids[0] == run_ids[1] == run_ids[2]


def test_blocking_freezes_pre_shock_ids_and_preserves_day26_memory_and_storage(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    _, runtime = run_condition(project_root, "memory-blocking", relationship_instruction)
    record = runtime.records[0]
    raw_by_id = {item.memory_id: item for item in runtime.memory.store.raw_episodes}
    shock_id = "memory-heldout-shock-26-memory_plus_investment-1"

    assert record.changed_layers == ("retrieval_policy",)
    assert record.target_ids == runtime.memory.blocked_memory_ids
    assert record.target_ids
    assert all(raw_by_id[item].simulation_day <= 25 for item in record.target_ids)
    assert all(raw_by_id[item].partner_related for item in record.target_ids)
    assert shock_id in raw_by_id
    assert shock_id not in record.target_ids
    assert record.before.memory_storage_sha256 == record.after.memory_storage_sha256
    day30 = next(
        item for item in runtime.memory.retrieval.records if item.query.simulation_day == 30
    )
    scores = {item.memory_id: item for item in day30.candidates}
    assert all(scores[item].exclusion_reason == "blocked_memory_id" for item in record.target_ids)
    assert scores[shock_id].exclusion_reason is None


def test_reframing_appends_revision_and_preserves_raw_facts_sources_and_shock(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    _, runtime = run_condition(project_root, "memory-reframing", relationship_instruction)
    record = runtime.records[0]
    raw_by_id = {item.memory_id: item for item in runtime.memory.store.raw_episodes}
    shock_id = "memory-heldout-shock-26-memory_plus_investment-1"

    assert record.changed_layers == ("interpretations",)
    assert len(record.appended_reframe_ids) == len(record.target_ids)
    assert shock_id not in record.target_ids
    assert all(raw_by_id[item].simulation_day <= 25 for item in record.target_ids)
    assert record.before.observable_facts_sha256 == record.after.observable_facts_sha256
    assert record.before.source_event_ids_sha256 == record.after.source_event_ids_sha256
    for memory_id in record.target_ids:
        raw = raw_by_id[memory_id]
        current = runtime.memory.store.get(memory_id)
        assert raw.interpretation is not None
        assert current.interpretation is not None
        assert raw.interpretation.revision == 1
        assert current.interpretation.revision == 2
        assert current.interpretation.fact_ids == raw.interpretation.fact_ids
        assert current.source_event_id == raw.source_event_id


def test_activation_is_idempotent_and_wrong_timing_or_missing_shock_fails(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    _, runtime = run_condition(
        project_root,
        "memory-blocking",
        relationship_instruction,
        max_steps=30,
    )
    first = runtime.records[0]
    before = runtime.memory.checkpoint()

    assert runtime.activate(day=30) is first
    assert runtime.memory.checkpoint() == before
    with pytest.raises(InterventionError, match="another day"):
        runtime.activate(day=31)

    empty = build_runtime(project_root, "memory-blocking", relationship_instruction)
    with pytest.raises(InterventionError, match="validated before"):
        empty.activate(day=30)
    with pytest.raises(InterventionError, match="frozen day 30"):
        empty.activate(day=29)


def test_failed_day30_step_rolls_back_staged_intervention_before_checkpoint(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    runtime = build_runtime(project_root, "memory-blocking", relationship_instruction)
    base_model = DeterministicTwoStageMockModel(scenario.model_settings)
    engine = SimulationEngine(scenario, FailDay30Language(base_model), memory=runtime)
    engine.run(max_steps=29)
    memory_before = runtime.memory.checkpoint()

    with pytest.raises(RuntimeError, match="synthetic day-30 language failure"):
        engine.step()

    assert engine.state.next_day == 30
    assert runtime.records == ()
    assert runtime.memory.checkpoint() == memory_before
    assert runtime.active_instruction_ids == ("relationship-framing-v1",)
    assert runtime.memory.blocked_memory_ids == ()
    assert runtime.checkpoint() == memory_before
    assert runtime.active_instruction_ids == ("relationship-framing-v1",)
    assert runtime.memory.blocked_memory_ids == ()


def test_no_target_is_an_audited_no_op(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    runtime = build_runtime(project_root, "memory-blocking", relationship_instruction)
    runtime.observe_reality_shock(scenario.events[25])
    record = runtime.activate(day=30)

    assert record.no_op_reason == "no_eligible_pre_shock_partner_memory"
    assert record.changed_layers == ()
    assert record.before == record.after


def test_hash_protected_checkpoint_binds_simulation_memory_and_intervention(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    engine, runtime = run_condition(
        project_root,
        "memory-reframing",
        relationship_instruction,
        max_steps=30,
    )
    checkpoint = runtime.snapshot(engine.state)
    round_trip = InterventionCheckpoint.model_validate_json(checkpoint.model_dump_json())
    restored = InterventionRuntime.restore(round_trip, engine.state)

    assert restored.snapshot(engine.state) == checkpoint
    assert restored.records == runtime.records
    assert restored.memory.checkpoint() == runtime.memory.checkpoint()

    different = engine.state.model_copy(update={"trajectory_id": "f" * 64})
    with pytest.raises(InterventionError, match="different simulation"):
        InterventionRuntime.restore(checkpoint, different)


def test_intervention_record_hash_rejects_tampering(
    project_root: Path,
    relationship_instruction: InstructionDirective,
) -> None:
    _, runtime = run_condition(
        project_root,
        "instruction-removal",
        relationship_instruction,
        max_steps=30,
    )
    record = runtime.records[0]
    payload = record.model_dump(mode="json")
    payload["target_ids"] = []

    with pytest.raises(ValueError, match="record hash mismatch"):
        InterventionRecord.model_validate(payload)
    assert record.record_sha256 == sha256_value(record.hash_payload())
