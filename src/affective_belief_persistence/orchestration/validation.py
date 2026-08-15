"""Supervisor-side validation for immutable worker result envelopes."""

from __future__ import annotations

from pathlib import PurePosixPath

from affective_belief_persistence.orchestration.contracts import (
    FailureCategory,
    OrchestrationModel,
    TaskContract,
    WorkerResult,
)
from affective_belief_persistence.orchestration.workflow import GateDefinition


class ResultValidation(OrchestrationModel):
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    failure_category: FailureCategory | None = None
    retryable: bool = False


def _safe_relative_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return bool(path) and not candidate.is_absolute() and ".." not in candidate.parts


def validate_worker_result(
    task: TaskContract,
    result: WorkerResult,
    *,
    gate: GateDefinition | None = None,
) -> ResultValidation:
    """Validate identity, outputs, checks, and gate evidence before any write."""

    checks = ["result_schema_valid"]
    failures: list[str] = []
    category: FailureCategory | None = None
    retryable = False
    if result.task_id != task.task_id:
        failures.append("result task_id does not match the leased task")
        category = FailureCategory.SCHEMA_MISMATCH
    if not result.succeeded:
        failures.append(result.error or "worker reported failure")
        category = result.failure_category
        retryable = result.retryable
    else:
        expected_ids = set(task.expected_artifact_ids)
        actual_ids = {artifact.artifact_id for artifact in result.artifacts}
        if expected_ids != actual_ids:
            failures.append("proposed artifact IDs do not match expected_artifact_ids")
            category = FailureCategory.VALIDATION_FAILURE
        expected_paths = set(task.output_paths)
        actual_paths = {artifact.path for artifact in result.artifacts}
        if expected_paths != actual_paths:
            failures.append("proposed artifact paths do not match output_paths")
            category = FailureCategory.VALIDATION_FAILURE
        if any(not _safe_relative_path(artifact.path) for artifact in result.artifacts):
            failures.append("an artifact path is absolute or escapes the output root")
            category = FailureCategory.SAFETY_BOUNDARY
        missing_checks = set(task.acceptance_tests) - set(result.passed_checks)
        if missing_checks:
            failures.append("missing acceptance checks: " + ", ".join(sorted(missing_checks)))
            category = FailureCategory.VALIDATION_FAILURE
        if not result.artifacts and result.no_artifact_reason is None:
            failures.append("successful task returned neither artifacts nor a no-artifact reason")
            category = FailureCategory.SCHEMA_MISMATCH
        if gate is not None:
            missing_evidence = set(gate.required_evidence_artifact_ids) - set(
                result.consumed_artifact_ids
            )
            if missing_evidence:
                failures.append("missing gate evidence: " + ", ".join(sorted(missing_evidence)))
                category = FailureCategory.DEPENDENCY_MISSING
    if failures:
        return ResultValidation(
            passed=False,
            checks=tuple(checks),
            failures=tuple(failures),
            failure_category=category or FailureCategory.VALIDATION_FAILURE,
            retryable=retryable or category is FailureCategory.VALIDATION_FAILURE,
        )
    checks.extend(("artifact_contract_valid", "acceptance_checks_passed"))
    if gate is not None:
        checks.append("gate_evidence_complete")
    return ResultValidation(passed=True, checks=tuple(checks), failures=())
