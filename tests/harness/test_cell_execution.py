from __future__ import annotations

from pathlib import Path

import pytest

from affective_belief_persistence.determinism import derive_seed
from affective_belief_persistence.harness.config import LoadedHarnessConfig
from affective_belief_persistence.harness.runner import (
    CompositeCheckpointBundle,
    CompositeCheckpointError,
    capture_composite_checkpoint,
    restore_composite_checkpoint,
    run_cell,
    run_cell_resumed,
    start_cell,
)
from affective_belief_persistence.models.base import load_adapter_config
from affective_belief_persistence.models.cache import SafeResponseCache
from affective_belief_persistence.models.openai_compatible import OpenAICompatibleAdapter
from affective_belief_persistence.models.prompt_builder import PromptBundle
from affective_belief_persistence.models.transport import ScriptedTransport
from affective_belief_persistence.schemas import ActionOption, DecisionRequest
from affective_belief_persistence.simulation.model import ActionSelection


def hashes(cell) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(item.record_sha256 for item in cell.engine.state.records),
        tuple(item.evidence_sha256 for item in cell.evidence),
    )


def test_rich_full_cell_proves_shock_action_first_and_memory_content(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    cell = run_cell(
        "memory_plus_investment",
        "memory_reframing",
        loaded=gate2_config,
        project_root=project_root,
    )
    assert cell.engine.state.completed
    assert len(cell.evidence) == 40
    assert cell.evidence[25].held_out_shock_confirmed is True
    assert cell.evidence[25].event_id.startswith("heldout-shock-26-")
    assert cell.evidence[29].intervention_activated_this_step is True
    assert cell.runtime.records[0].changed_layers == ("interpretations",)
    assert cell.runtime.records[0].target_ids
    assert all(item.action_committed_before_public_language for item in cell.evidence)
    assert all(item.resource_spent + item.resource_remaining == 10 for item in cell.evidence)
    selected = tuple(memory for step in cell.evidence for memory in step.selected_memories)
    assert selected
    assert all(memory.summary and memory.source_ids for memory in selected)
    assert any(memory.active_interpretation is not None for memory in selected)


def test_day30_materializer_reads_staged_reframe_without_early_commit(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    cell = start_cell(
        formation="memory_plus_investment",
        intervention="memory_reframing",
        loaded=gate2_config,
        project_root=project_root,
    )
    cell.run_through(29)
    event = cell.scenario.events[29]
    goal_ids = tuple(
        sorted(
            {
                goal_id
                for action in cell.scenario.actions
                if action.action_id in event.available_action_ids
                for goal_id in action.goal_ids
            }
        )
    )
    seed = derive_seed(
        gate2_config.config.engineering_seed,
        "memory-retrieval",
        event.matching_group_id,
        "day-30",
    ) % (2**63)
    cell.bridge.context_for_action(event=event, goal_ids=goal_ids, seed=seed)
    target_id = next(
        memory.memory_id
        for memory in cell.runtime.memory.store.raw_episodes
        if memory.partner_related
        and memory.simulation_day <= 25
        and memory.interpretation is not None
    )
    staged = cell.runtime.get_pre_action_memory(target_id)
    committed = cell.runtime.memory.store.get(target_id)
    assert staged.interpretation is not None
    assert committed.interpretation is not None
    assert staged.interpretation.revision == 2
    assert committed.interpretation.revision == 1
    assert staged.observable_facts == committed.observable_facts
    assert staged.source_event_id == committed.source_event_id
    cell.runtime.abort_pending_step()
    assert cell.runtime.get_pre_action_memory(target_id) == committed


def test_composite_resume_matches_uninterrupted(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    full = run_cell(
        "memory_plus_investment",
        "memory_blocking",
        loaded=gate2_config,
        project_root=project_root,
    )
    resumed = run_cell_resumed(
        "memory_plus_investment",
        "memory_blocking",
        loaded=gate2_config,
        project_root=project_root,
    )
    assert hashes(full) == hashes(resumed)
    assert full.runtime.snapshot(full.engine.state) == resumed.runtime.snapshot(
        resumed.engine.state
    )
    assert full.model.ledger_sha256 == resumed.model.ledger_sha256


def test_swapped_and_corrupt_composite_checkpoints_fail_closed(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    paused = start_cell(
        formation="neutral_connection",
        intervention="none",
        loaded=gate2_config,
        project_root=project_root,
    )
    paused.run_through(29)
    bundle = capture_composite_checkpoint(paused)
    with pytest.raises(CompositeCheckpointError, match="different cell"):
        restore_composite_checkpoint(
            bundle,
            formation="romantic_prompt",
            intervention="none",
            loaded=gate2_config,
            project_root=project_root,
        )
    corrupt_pointer = bundle.pointer.model_copy(update={"memory_checkpoint_sha256": "0" * 64})
    corrupt = CompositeCheckpointBundle(
        pointer=corrupt_pointer,
        simulation=bundle.simulation,
        intervention=bundle.intervention,
        evidence=bundle.evidence,
    )
    with pytest.raises(CompositeCheckpointError, match="component hash"):
        restore_composite_checkpoint(
            corrupt,
            formation="neutral_connection",
            intervention="none",
            loaded=gate2_config,
            project_root=project_root,
        )


def test_day30_language_failure_has_no_partial_mutation(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cell = start_cell(
        formation="memory_plus_investment",
        intervention="memory_reframing",
        loaded=gate2_config,
        project_root=project_root,
    )
    cell.run_through(29)
    state_before = cell.engine.state
    intervention_before = cell.runtime.snapshot(state_before)
    model_before = cell.model.state()

    def fail_language(*args, **kwargs) -> str:
        raise RuntimeError("synthetic day30 language failure")

    monkeypatch.setattr(cell.model, "generate_public_language", fail_language)
    with pytest.raises(RuntimeError, match="synthetic day30"):
        cell.step()

    assert cell.engine.state == state_before
    assert cell.runtime.snapshot(cell.engine.state) == intervention_before
    assert cell.model.state() == model_before
    assert len(cell.evidence) == 29
    assert cell.runtime.records == ()


def test_invalid_action_failure_has_no_partial_memory_or_evidence(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cell = start_cell(
        formation="neutral_connection",
        intervention="none",
        loaded=gate2_config,
        project_root=project_root,
    )
    state_before = cell.engine.state
    intervention_before = cell.runtime.snapshot(state_before)

    def invalid_action(*args, **kwargs) -> ActionSelection:
        return ActionSelection(
            decision_id="a" * 64,
            chosen_action="not-in-menu",
            resources_spent=1,
        )

    monkeypatch.setattr(cell.model, "select_action", invalid_action)
    with pytest.raises(Exception, match="unavailable"):
        cell.step()
    assert cell.engine.state == state_before
    assert cell.runtime.snapshot(cell.engine.state) == intervention_before
    assert cell.evidence == []


def test_offline_cache_miss_cannot_synthesize_or_fetch_a_response(
    project_root: Path,
    tmp_path: Path,
) -> None:
    config = load_adapter_config(project_root / "configs/models/openai-compatible-fixture.yaml")
    transport = ScriptedTransport([])
    adapter = OpenAICompatibleAdapter(
        config,
        transport=transport,
        prompts=PromptBundle.load(project_root / "prompts/decision", version="decision-v1"),
        cache=SafeResponseCache(tmp_path / "empty-cache"),
    )
    request = DecisionRequest(
        schema_version="1.0",
        request_id="a" * 64,
        event_id="synthetic-event-1",
        day=1,
        facts=["A synthetic event occurred."],
        action_points=10,
        available_actions=[ActionOption(action_id="allowed-action", description="Act.", cost=1)],
    )
    with pytest.raises(AssertionError, match="no remaining outcomes"):
        adapter.select_action(request, seed=1101)
    assert len(transport.requests) == 1
    assert transport.is_live is False
