from __future__ import annotations

import threading
import time
from pathlib import Path

from affective_belief_persistence.orchestration.budgets import BudgetLimits
from affective_belief_persistence.orchestration.contracts import (
    TaskBudget,
    TaskContract,
    TaskStatus,
    WorkerResult,
)
from affective_belief_persistence.orchestration.scheduler import (
    Supervisor,
    SyntheticWorkflowExecutor,
)
from affective_belief_persistence.orchestration.workflow import (
    GateDefinition,
    LoadedWorkflow,
    WorkflowDefinition,
    load_workflow_definition,
)


def _task(
    task_id: str,
    *,
    role: str,
    task_type: str,
    area: str,
    dependencies: tuple[str, ...] = (),
    gate_id: str | None = None,
    input_ids: tuple[str, ...] = (),
) -> TaskContract:
    artifact_id = f"{task_id}-artifact"
    path = f"artifacts/{area}/{task_id}.json"
    return TaskContract(
        task_id=task_id,
        title=task_id,
        owner=role,
        task_type=task_type,
        gate_id=gate_id,
        dependencies=dependencies,
        authorized_files=(path,),
        output_paths=(path,),
        input_artifact_ids=input_ids,
        expected_artifact_ids=(artifact_id,),
        acceptance_tests=("contract_passed",),
        budget=TaskBudget(max_runtime_seconds=60, max_tokens=100),
    )


def _small_workflow(project_root: Path) -> LoadedWorkflow:
    first = _task("first", role="research", task_type="literature_review", area="research")
    data = _task(
        "data",
        role="data",
        task_type="scenario_design",
        area="data",
        dependencies=("first",),
        input_ids=("first-artifact",),
    )
    code = _task(
        "code",
        role="engineering",
        task_type="implementation",
        area="engineering",
        dependencies=("first",),
        input_ids=("first-artifact",),
    )
    review = _task(
        "review",
        role="reviewer",
        task_type="claim_audit",
        area="reviews",
        dependencies=("first",),
        input_ids=("first-artifact",),
    )
    gate = _task(
        "gate",
        role="supervisor",
        task_type="integration_gate",
        area="orchestration",
        dependencies=("data", "code", "review"),
        gate_id="gate-test",
        input_ids=("data-artifact", "code-artifact", "review-artifact"),
    )
    definition = WorkflowDefinition(
        workflow_id="test-workflow",
        sprint_id="test-sprint",
        seed=42,
        created_at="2026-08-15T00:00:00Z",
        agent_registry="configs/agents/registry.yaml",
        max_workers=3,
        limits=BudgetLimits(max_wall_clock_seconds=1000, max_tokens=10000),
        tasks=(first, data, code, review, gate),
        gates=(
            GateDefinition(
                gate_id="gate-test",
                name="Test gate",
                task_id="gate",
                required_evidence_artifact_ids=(
                    "data-artifact",
                    "code-artifact",
                    "review-artifact",
                ),
            ),
        ),
        final_task_id="gate",
    )
    return LoadedWorkflow(
        definition=definition,
        project_root=project_root,
        source_path=project_root / "configs/workflows/test.yaml",
        registry_path=project_root / "configs/agents/registry.yaml",
        config_sha256="0" * 64,
    )


class _ConcurrencyExecutor:
    def __init__(self) -> None:
        self._delegate = SyntheticWorkflowExecutor()
        self._lock = threading.Lock()
        self.active = 0
        self.maximum = 0
        self.calls: list[str] = []

    def run(
        self,
        task: TaskContract,
        *,
        input_artifact_ids: tuple[str, ...],
        seed: int,
        attempt: int,
    ) -> WorkerResult:
        with self._lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.calls.append(task.task_id)
        time.sleep(0.02)
        try:
            return self._delegate.run(
                task,
                input_artifact_ids=input_artifact_ids,
                seed=seed,
                attempt=attempt,
            )
        finally:
            with self._lock:
                self.active -= 1


def test_scheduler_enforces_dependencies_and_three_worker_limit(
    project_root: Path, tmp_path: Path
) -> None:
    executor = _ConcurrencyExecutor()
    supervisor = Supervisor(_small_workflow(project_root), tmp_path / "run", executor=executor)
    summary = supervisor.run()

    assert summary.status == "completed"
    assert executor.maximum == 3
    assert executor.calls[0] == "first"
    assert executor.calls[-1] == "gate"
    assert all(supervisor.state.gates.values())


def test_retry_exhaustion_prevents_a_third_automatic_attempt(
    project_root: Path, tmp_path: Path
) -> None:
    executor = SyntheticWorkflowExecutor(fail_through_attempt={"first": 10})
    supervisor = Supervisor(_small_workflow(project_root), tmp_path / "run", executor=executor)
    summary = supervisor.run()
    task = supervisor.state.tasks["first"]

    assert summary.status == "failed"
    assert task.status is TaskStatus.ESCALATED
    assert task.attempt_count == 2
    assert task.retry_count == 1
    assert supervisor.state.tasks["gate"].attempt_count == 0


def test_checkpoint_resume_does_not_repeat_completed_tasks(
    project_root: Path, tmp_path: Path
) -> None:
    output = tmp_path / "run"
    first_executor = _ConcurrencyExecutor()
    first = Supervisor(_small_workflow(project_root), output, executor=first_executor)
    paused = first.run(max_waves=1)
    second_executor = _ConcurrencyExecutor()
    resumed = Supervisor(
        _small_workflow(project_root), output, executor=second_executor, resume=True
    )
    completed = resumed.run()

    assert paused.status == "paused"
    assert completed.status == "completed"
    assert first_executor.calls == ["first"]
    assert "first" not in second_executor.calls
    assert resumed.state.tasks["first"].attempt_count == 1


def test_full_sprint_zero_gpu_fallback_and_deterministic_replay(
    project_root: Path, tmp_path: Path
) -> None:
    loaded = load_workflow_definition(
        project_root / "configs/workflows/forty_eight_hour_sprint.yaml"
    )
    first = Supervisor(loaded, tmp_path / "first")
    second = Supervisor(loaded, tmp_path / "second")
    first_summary = first.run()
    second_summary = second.run()

    assert first_summary.status == "completed"
    assert first_summary.state_sha256 == second_summary.state_sha256
    assert first.state.tasks["issue-13-training"].status is TaskStatus.CANCELLED
    assert first.state.tasks["issue-14-experiment"].status is TaskStatus.COMPLETED
    assert first.state.tasks["final-synthesis"].status is TaskStatus.COMPLETED
    assert all(first.state.gates.values())


class _LeakageFailureExecutor(SyntheticWorkflowExecutor):
    def run(
        self,
        task: TaskContract,
        *,
        input_artifact_ids: tuple[str, ...],
        seed: int,
        attempt: int,
    ) -> WorkerResult:
        result = super().run(
            task,
            input_artifact_ids=input_artifact_ids,
            seed=seed,
            attempt=attempt,
        )
        if task.task_id != "issue-8-dataset":
            return result
        return result.model_copy(
            update={
                "passed_checks": tuple(
                    check for check in result.passed_checks if check != "separation_leakage_absent"
                )
            }
        )


def test_leakage_acceptance_failure_blocks_release(project_root: Path, tmp_path: Path) -> None:
    loaded = load_workflow_definition(
        project_root / "configs/workflows/forty_eight_hour_sprint.yaml"
    )
    supervisor = Supervisor(loaded, tmp_path / "run", executor=_LeakageFailureExecutor())
    summary = supervisor.run()

    assert summary.status == "failed"
    assert supervisor.state.tasks["issue-8-dataset"].status is TaskStatus.ESCALATED
    assert supervisor.state.tasks["issue-8-dataset"].attempt_count == 2
    assert supervisor.state.tasks["gate-1-data"].status is TaskStatus.ESCALATED
    assert not supervisor.state.gates["gate-1"]


def test_corrupt_checkpoint_fails_safely(project_root: Path, tmp_path: Path) -> None:
    output = tmp_path / "run"
    output.mkdir()
    (output / "workflow-state.json").write_text("{not-json", encoding="utf-8")
    loaded = _small_workflow(project_root)

    try:
        Supervisor(loaded, output, resume=True)
    except RuntimeError as exc:
        assert "invalid workflow checkpoint" in str(exc)
    else:
        raise AssertionError("corrupt checkpoint was accepted")
