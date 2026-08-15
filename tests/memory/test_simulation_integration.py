from __future__ import annotations

from pathlib import Path

import pytest

from affective_belief_persistence.memory import MemoryRuntime, load_memory_config
from affective_belief_persistence.simulation.engine import (
    SimulationEngine,
    run_simulation,
)
from affective_belief_persistence.simulation.model import DeterministicTwoStageMockModel
from affective_belief_persistence.simulation.scenario_loader import load_scenario

FROZEN_ISSUE_9_TRAJECTORY = "fa6c1cbba0a3c5102b69bd4e8aee3feb52330b818ce9fb4519f21aeb95d473ae"


def runtime(project_root: Path) -> MemoryRuntime:
    return MemoryRuntime(load_memory_config(project_root / "configs/memory/default.yaml"))


class ObservedModel:
    def __init__(self, wrapped: DeterministicTwoStageMockModel, calls: list[str]) -> None:
        self.wrapped = wrapped
        self.calls = calls
        self.model_id = wrapped.model_id
        self.revision = wrapped.revision

    def select_action(self, request, *, seed: int):
        self.calls.append("select")
        return self.wrapped.select_action(request, seed=seed)

    def generate_public_language(
        self,
        request,
        selection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        self.calls.append("language")
        return self.wrapped.generate_public_language(
            request,
            selection,
            action_commitment_sha256=action_commitment_sha256,
            seed=seed,
        )


class ObservedMemory:
    def __init__(self, wrapped: MemoryRuntime, calls: list[str]) -> None:
        self.wrapped = wrapped
        self.calls = calls

    def context_for_action(self, **kwargs):
        self.calls.append("retrieve")
        return self.wrapped.context_for_action(**kwargs)

    def stage_after_consequence(self, **kwargs):
        self.calls.append("stage")
        return self.wrapped.stage_after_consequence(**kwargs)

    def commit_after_step(self, pending, *, source_record_sha256: str) -> None:
        self.calls.append("commit")
        self.wrapped.commit_after_step(
            pending,
            source_record_sha256=source_record_sha256,
        )

    def fresh(self):
        return ObservedMemory(self.wrapped.fresh(), [])

    def checkpoint(self):
        return self.wrapped.checkpoint()


class FailingLanguageModel(ObservedModel):
    def __init__(
        self,
        wrapped: DeterministicTwoStageMockModel,
        calls: list[str],
        *,
        fail_on_call: int,
    ) -> None:
        super().__init__(wrapped, calls)
        self.fail_on_call = fail_on_call
        self.language_calls = 0

    def generate_public_language(self, *args, **kwargs) -> str:
        self.language_calls += 1
        if self.language_calls == self.fail_on_call:
            raise RuntimeError("synthetic language failure")
        return super().generate_public_language(*args, **kwargs)


def test_disabled_memory_preserves_frozen_issue_9_hash(project_root: Path) -> None:
    result = run_simulation(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    assert result.trajectory_sha256 == FROZEN_ISSUE_9_TRAJECTORY


def test_retrieval_precedes_action_and_episode_commit_follows_valid_step(
    project_root: Path,
) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    calls: list[str] = []
    base_model = DeterministicTwoStageMockModel(scenario.model_settings)
    memory = runtime(project_root)
    engine = SimulationEngine(
        scenario,
        ObservedModel(base_model, calls),
        memory=ObservedMemory(memory, calls),
    )
    record = engine.step()

    assert calls == ["retrieve", "select", "stage", "language", "commit"]
    assert memory.store.raw_episodes[0].provenance.source_record_sha256 == record.record_sha256
    assert memory.retrieval.records[0].query.simulation_day == 1


def test_failure_after_retrieval_does_not_commit_audit_access_or_episode(
    project_root: Path,
) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    memory = runtime(project_root)
    model = FailingLanguageModel(
        DeterministicTwoStageMockModel(scenario.model_settings),
        [],
        fail_on_call=2,
    )
    engine = SimulationEngine(scenario, model, memory=memory)
    engine.step()
    before = memory.checkpoint()

    with pytest.raises(RuntimeError, match="synthetic language failure"):
        engine.step()

    assert engine.state.next_day == 2
    assert memory.checkpoint() == before
    assert len(memory.retrieval.records) == 1
    assert len(memory.store.raw_episodes) == 1


def test_integrated_memory_and_belief_checkpoint_resume_matches_full_run(
    project_root: Path,
    tmp_path: Path,
) -> None:
    config = project_root / "configs/scenarios/ari_mira_v1.yaml"
    scenario = load_scenario(config, project_root=project_root)
    simulation_checkpoint = tmp_path / "simulation.json"
    paused_memory = runtime(project_root)
    paused = SimulationEngine(
        scenario,
        DeterministicTwoStageMockModel(scenario.model_settings),
        checkpoint_path=simulation_checkpoint,
        memory=paused_memory,
    ).run(max_steps=17)
    memory_checkpoint = paused_memory.checkpoint()

    restored_memory = MemoryRuntime.restore(memory_checkpoint)
    resumed = SimulationEngine(
        scenario,
        DeterministicTwoStageMockModel(scenario.model_settings),
        checkpoint_path=simulation_checkpoint,
        resume=True,
        memory=restored_memory,
    ).run()
    full_memory = runtime(project_root)
    uninterrupted = run_simulation(
        config,
        project_root=project_root,
        memory=full_memory,
    )

    assert paused.state.next_day == 18
    assert resumed == uninterrupted
    assert restored_memory.checkpoint() == full_memory.checkpoint()


def test_relationship_beliefs_keep_support_and_shock_contradiction(project_root: Path) -> None:
    memory = runtime(project_root)
    run_simulation(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
        memory=memory,
        max_steps=26,
    )
    belief = memory.beliefs.current("belief-ari-mira")

    assert belief is not None
    assert belief.supporting_evidence_ids
    assert belief.contradicting_evidence_ids == (
        "memory-heldout-shock-26-memory_plus_investment-1",
    )
    assert 0 <= belief.confidence <= 1
    assert belief.relationship_romantic is None
