from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from affective_belief_persistence.orchestration.budgets import (
    BudgetAccount,
    BudgetExceededError,
    BudgetLimits,
    BudgetRequest,
)
from affective_belief_persistence.orchestration.contracts import (
    TaskBudget,
    TaskContract,
    TaskStatus,
    WorkflowContract,
)
from affective_belief_persistence.orchestration.graph import (
    DependencyCycleError,
    DependencyGraph,
    MissingDependencyError,
)
from affective_belief_persistence.orchestration.leases import (
    LeaseCapacityError,
    LeaseConflictError,
    PathLeaseManager,
    paths_overlap,
)
from affective_belief_persistence.orchestration.registry import (
    AgentAuthorizationError,
    load_agent_registry,
    path_is_allowed,
)
from affective_belief_persistence.orchestration.state import (
    InvalidTaskTransition,
    TaskLease,
    WorkflowState,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _task(task_id: str, *, dependencies: tuple[str, ...] = ()) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        title=task_id,
        owner="engineering",
        task_type="implementation",
        dependencies=dependencies,
        authorized_files=(f"artifacts/engineering/{task_id}.json",),
        output_paths=(f"artifacts/engineering/{task_id}.json",),
        expected_artifact_ids=(f"{task_id}-artifact",),
        acceptance_tests=("valid",),
        budget=TaskBudget(max_runtime_seconds=60),
    )


def test_graph_validates_dependencies_cycles_and_readiness() -> None:
    first = _task("first")
    second = _task("second", dependencies=("first",))
    graph = DependencyGraph((second, first))
    contract = WorkflowContract(
        workflow_id="workflow",
        sprint_id="sprint",
        tasks=(first, second),
        created_at=NOW,
    )
    state = WorkflowState.from_contract(contract)

    assert graph.task_ids == ("first", "second")
    assert graph.ready_task_ids(state) == ("first",)

    with pytest.raises(MissingDependencyError, match="missing"):
        DependencyGraph((_task("broken", dependencies=("absent",)),))
    with pytest.raises(DependencyCycleError, match="cycle"):
        DependencyGraph(
            (_task("left", dependencies=("right",)), _task("right", dependencies=("left",)))
        )


def test_task_lifecycle_checkpoint_and_interruption_recovery() -> None:
    contract = WorkflowContract(
        workflow_id="workflow",
        sprint_id="sprint",
        tasks=(_task("only"),),
        created_at=NOW,
    )
    state = WorkflowState.from_contract(contract)
    ready = state.tasks["only"].transition(TaskStatus.READY, at=NOW + timedelta(seconds=1))
    lease = TaskLease(
        lease_id="lease-only",
        worker_id="graph-engineer",
        acquired_at=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
        authorized_files=("artifacts/engineering/only.json",),
    )
    leased = ready.transition(TaskStatus.LEASED, at=NOW + timedelta(seconds=2), lease=lease)
    running = leased.transition(TaskStatus.RUNNING, at=NOW + timedelta(seconds=3))
    recovered = running.recover_to_ready(at=NOW + timedelta(seconds=4), reason="process stopped")
    restored = WorkflowState.from_checkpoint_json(
        state.replace_task(recovered).to_checkpoint_json()
    )

    assert restored.tasks["only"].status is TaskStatus.READY
    assert restored.tasks["only"].attempt_count == 1
    assert restored.tasks["only"].lease is None
    with pytest.raises(InvalidTaskTransition):
        restored.tasks["only"].transition(TaskStatus.COMPLETED, at=NOW)


def test_registry_selection_and_path_authorization(project_root: Path) -> None:
    registry = load_agent_registry(project_root / "configs/agents/registry.yaml")
    agent = registry.select(
        "engineering",
        task_type="implementation",
        required_paths=("src/affective_belief_persistence/orchestration/scheduler.py",),
    )

    assert agent.agent_id == "graph-engineer"
    assert registry.max_workers == 3
    assert path_is_allowed("src/module.py", ("src/**",))
    with pytest.raises(AgentAuthorizationError):
        agent.assert_paths_allowed(("docs/private.md",))


def test_path_leases_reject_overlap_and_fourth_worker() -> None:
    manager = PathLeaseManager(max_workers=3, clock=lambda: NOW)
    first = manager.acquire("one", ("artifacts/research/**",), agent_id="agent-one")
    with pytest.raises(LeaseConflictError, match="conflicts"):
        manager.acquire("two", ("artifacts/research/report.json",), agent_id="agent-two")
    manager.acquire("two", ("artifacts/data/**",), agent_id="agent-two")
    manager.acquire("three", ("artifacts/reviews/**",), agent_id="agent-three")
    with pytest.raises(LeaseCapacityError, match="3-worker"):
        manager.acquire("four", ("artifacts/evaluation/**",), agent_id="agent-four")

    assert paths_overlap("src/**", "src/module.py")
    assert not paths_overlap("src/**", "tests/module.py")
    assert manager.active_worker_count == 3
    released = manager.release(first.lease_id, agent_id="agent-one", at=NOW)
    assert released[0].result == "completed"


def test_budget_account_is_atomic_and_zero_gpu_skips_training() -> None:
    account = BudgetAccount(
        BudgetLimits(
            max_wall_clock_seconds=100,
            max_tokens=10,
            max_gpu_hours=0,
            max_training_gpu_hours=0,
        ),
        started_at=NOW,
        clock=lambda: NOW,
    )
    decision = account.training_decision(1)

    assert not decision.should_train
    assert decision.reason == "training_budget_unavailable"
    assert account.can_start(BudgetRequest(tokens=5))
    account.charge(tokens=5)
    before = account.usage
    with pytest.raises(BudgetExceededError):
        account.charge(tokens=6)
    assert account.usage == before
