"""Validated dependency graph and deterministic readiness calculation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from affective_belief_persistence.orchestration.contracts import TaskContract, TaskStatus
from affective_belief_persistence.orchestration.state import WorkflowState, WorkflowTask


class DependencyGraphError(ValueError):
    """Base error for an invalid workflow dependency graph."""


class MissingDependencyError(DependencyGraphError):
    """Raised when a task references an undeclared dependency."""


class DependencyCycleError(DependencyGraphError):
    """Raised when the workflow dependency graph contains a cycle."""


class DependencyGraph:
    """Immutable view of task dependencies with stable scheduler ordering."""

    def __init__(self, tasks: Iterable[TaskContract]) -> None:
        task_list = tuple(tasks)
        self._tasks = {task.task_id: task for task in task_list}
        if len(self._tasks) != len(task_list):
            raise DependencyGraphError("task IDs must be unique")
        self._validate_dependencies()
        self._topological_order = self._calculate_topological_order()

    @property
    def task_ids(self) -> tuple[str, ...]:
        """Task IDs in deterministic topological order."""

        return self._topological_order

    def task(self, task_id: str) -> TaskContract:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown task: {task_id}") from exc

    def dependencies_of(self, task_id: str) -> tuple[str, ...]:
        return self.task(task_id).dependencies

    def optional_dependencies_of(self, task_id: str) -> tuple[str, ...]:
        return self.task(task_id).optional_dependencies

    def _validate_dependencies(self) -> None:
        known = set(self._tasks)
        missing = sorted(
            {
                dependency
                for task in self._tasks.values()
                for dependency in (*task.dependencies, *task.optional_dependencies)
                if dependency not in known
            }
        )
        if missing:
            raise MissingDependencyError(f"missing dependencies: {', '.join(missing)}")

    def _calculate_topological_order(self) -> tuple[str, ...]:
        indegree = {task_id: 0 for task_id in self._tasks}
        dependents: dict[str, list[str]] = {task_id: [] for task_id in self._tasks}
        for task in self._tasks.values():
            all_dependencies = (*task.dependencies, *task.optional_dependencies)
            indegree[task.task_id] = len(all_dependencies)
            for dependency in all_dependencies:
                dependents[dependency].append(task.task_id)

        available = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
        ordered: list[str] = []
        while available:
            task_id = available.pop(0)
            ordered.append(task_id)
            for dependent in sorted(dependents[task_id]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    available.append(dependent)
                    available.sort()

        if len(ordered) != len(self._tasks):
            cyclic = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
            raise DependencyCycleError(f"dependency cycle involves: {', '.join(cyclic)}")
        return tuple(ordered)

    def validate_state(self, state: WorkflowState) -> None:
        """Reject state built for a different task graph."""

        expected = set(self._tasks)
        actual = set(state.tasks)
        if expected != actual:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            details: list[str] = []
            if missing:
                details.append(f"missing state: {', '.join(missing)}")
            if unexpected:
                details.append(f"unexpected state: {', '.join(unexpected)}")
            raise DependencyGraphError("; ".join(details))

    def dependencies_completed(self, task_id: str, states: Mapping[str, WorkflowTask]) -> bool:
        """Return whether every direct dependency completed successfully."""

        required = self.dependencies_of(task_id)
        optional = self.optional_dependencies_of(task_id)
        missing_states = [
            dependency for dependency in (*required, *optional) if dependency not in states
        ]
        if missing_states:
            raise DependencyGraphError(
                f"missing task state for dependencies: {', '.join(sorted(missing_states))}"
            )
        return all(
            states[dependency].status is TaskStatus.COMPLETED for dependency in required
        ) and all(
            states[dependency].status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
            for dependency in optional
        )

    def ready_task_ids(self, state: WorkflowState) -> tuple[str, ...]:
        """Return schedulable tasks in deterministic topological order.

        PENDING and RETRY tasks become eligible once all dependencies complete;
        already-marked READY tasks remain schedulable.  Active, blocked,
        escalated, completed, and cancelled tasks are never returned.
        """

        self.validate_state(state)
        candidates = {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RETRY}
        return tuple(
            task_id
            for task_id in self._topological_order
            if state.tasks[task_id].status in candidates
            and self.dependencies_completed(task_id, state.tasks)
        )
