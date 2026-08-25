"""Hash-bound Gate 3 preflight with an explicit nonpassing evidence path."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from affective_belief_persistence.config import load_yaml
from affective_belief_persistence.determinism import sha256_file, sha256_value
from affective_belief_persistence.evaluation.config import load_evaluation_config
from affective_belief_persistence.evaluation.matrix import expand_experiment_matrix
from affective_belief_persistence.gate3.contracts import (
    AuthorizationDecision,
    CheckStatus,
    Gate3Authorization,
    Gate3CallBudgetAmendment,
    Gate3Evidence,
    Gate3PreflightResult,
    Gate3SourceLocks,
    PilotIntegritySummary,
    PreflightCheck,
)
from affective_belief_persistence.models.base import load_adapter_config


class Gate3PreflightError(RuntimeError):
    """The Gate 3 boundary is unsafe, corrupt, or not authorized."""


PROMPT_BUNDLE_PATHS = (
    "prompts/decision/v1.action.md",
    "prompts/decision/v1.language.md",
    "prompts/decision/v1.repair.md",
)
METRIC_BUNDLE_PATHS = (
    "src/affective_belief_persistence/evaluation/contracts.py",
    "src/affective_belief_persistence/evaluation/metrics.py",
    "src/affective_belief_persistence/evaluation/registry.py",
)
PILOT_TRAJECTORY_DAYS = 40
MINIMUM_PROVIDER_CALLS_PER_DAY = 2
CALL_BUDGET_AMENDMENT_PATH = "configs/gate3/call-budget-amendment.yaml"


def _regular_file(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise Gate3PreflightError(f"Gate 3 path must be repository-relative: {relative}")
    candidate = root / relative
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or candidate.is_symlink() or not resolved.is_file():
        raise Gate3PreflightError(f"Gate 3 input must be a regular repository file: {relative}")
    return resolved


def _bundle_sha256(root: Path, relatives: tuple[str, ...]) -> str:
    return sha256_value(
        {relative: sha256_file(_regular_file(root, relative)) for relative in relatives}
    )


def collect_source_locks(project_root: Path) -> Gate3SourceLocks:
    """Compute every non-model input lock required before the pilot."""

    root = project_root.resolve()
    loaded = load_evaluation_config(
        root / "configs/evaluation/default.yaml",
        project_root=root,
    )
    pilot = expand_experiment_matrix(loaded, "pilot")
    return Gate3SourceLocks(
        issue14_artifact_sha256=sha256_file(
            _regular_file(root, "artifacts/evaluation/issue-14-metrics.json")
        ),
        gate1_artifact_sha256=sha256_file(
            _regular_file(root, "artifacts/orchestration/gate-1.json")
        ),
        gate2_artifact_sha256=sha256_file(
            _regular_file(root, "artifacts/orchestration/gate-2.json")
        ),
        evaluation_config_sha256=loaded.config_sha256,
        pilot_config_sha256=loaded.experiment_sha256["pilot"],
        dataset_manifest_sha256=sha256_file(
            _regular_file(root, "data/manifests/dataset-manifest.json")
        ),
        prompt_bundle_sha256=_bundle_sha256(root, PROMPT_BUNDLE_PATHS),
        metric_bundle_sha256=_bundle_sha256(root, METRIC_BUNDLE_PATHS),
        pilot_matrix_sha256=pilot.matrix_sha256,
        call_budget_amendment_sha256=sha256_file(_regular_file(root, CALL_BUDGET_AMENDMENT_PATH)),
    )


def load_gate3_authorization(path: Path, *, project_root: Path) -> Gate3Authorization:
    root = project_root.resolve()
    allowed = (root / "configs/gate3").resolve()
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(allowed) or not resolved.is_file():
        raise Gate3PreflightError("Gate 3 authorization must be a regular file under configs/gate3")
    try:
        return Gate3Authorization.model_validate(load_yaml(resolved))
    except (OSError, ValueError, ValidationError) as exc:
        raise Gate3PreflightError(f"invalid Gate 3 authorization {path}: {exc}") from exc


def load_gate3_call_budget_amendment(
    path: Path,
    *,
    project_root: Path,
) -> Gate3CallBudgetAmendment:
    root = project_root.resolve()
    expected = (root / CALL_BUDGET_AMENDMENT_PATH).resolve()
    resolved = path.resolve()
    if path.is_symlink() or resolved != expected or not resolved.is_file():
        raise Gate3PreflightError(
            f"Gate 3 call-budget amendment must be the regular file {CALL_BUDGET_AMENDMENT_PATH}"
        )
    try:
        return Gate3CallBudgetAmendment.model_validate(load_yaml(resolved))
    except (OSError, ValueError, ValidationError) as exc:
        raise Gate3PreflightError(f"invalid Gate 3 call-budget amendment {path}: {exc}") from exc


def _accepted_issue14(root: Path) -> bool:
    path = _regular_file(root, "artifacts/evaluation/issue-14-metrics.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Gate3PreflightError(f"invalid Issue #14 evidence: {exc}") from exc
    expected = {
        "artifact_id": "issue-14-metric-spec",
        "task_id": "issue-14-metrics",
        "status": "accepted",
        "scientific_results": False,
        "live_calls": 0,
        "paid_calls": 0,
        "primary_outcomes_generated": False,
    }
    return isinstance(payload, dict) and all(
        payload.get(key) == value for key, value in expected.items()
    )


def _model_adapter_ready(authorization: Gate3Authorization, root: Path) -> bool:
    binding = authorization.model
    if not binding.resolved or binding.adapter_config_path is None:
        return False
    try:
        path = _regular_file(root, binding.adapter_config_path)
        adapter = load_adapter_config(path)
    except (Gate3PreflightError, ValueError):
        return False
    return (
        binding.adapter_config_sha256 == sha256_file(path)
        and adapter.provider.value == binding.provider
        and adapter.model_id == binding.model_id
        and adapter.revision == binding.revision
        and adapter.live_calls_enabled
        and adapter.prompt_version == "decision-v1"
        and adapter.inference.structured_json
    )


def _pilot_call_budget_feasible(
    authorization: Gate3Authorization,
    *,
    amendment: Gate3CallBudgetAmendment,
    assignment_count: int,
) -> bool:
    minimum_calls = assignment_count * PILOT_TRAJECTORY_DAYS * MINIMUM_PROVIDER_CALLS_PER_DAY
    return (
        authorization.budget is not None
        and authorization.budget.max_model_calls >= minimum_calls
        and authorization.budget.max_model_calls <= amendment.approved_max_model_calls
    )


def _call_budget_amendment_applies(
    amendment: Gate3CallBudgetAmendment,
    *,
    configured_max_calls: int,
    assignment_count: int,
) -> bool:
    return (
        configured_max_calls == amendment.previous_max_model_calls
        and assignment_count == amendment.assigned_trajectories
        and PILOT_TRAJECTORY_DAYS == amendment.trajectory_days
        and MINIMUM_PROVIDER_CALLS_PER_DAY == amendment.provider_stages_per_day
    )


def run_gate3_preflight(
    authorization: Gate3Authorization,
    *,
    project_root: Path,
    environment_names: set[str] | None = None,
    runtime_available: bool = False,
    current_code_commit_sha: str | None = None,
    now: datetime | None = None,
) -> Gate3PreflightResult:
    """Evaluate authorization and immutable inputs without invoking a provider."""

    root = project_root.resolve()
    call_budget_amendment = load_gate3_call_budget_amendment(
        root / CALL_BUDGET_AMENDMENT_PATH,
        project_root=root,
    )
    actual_locks = collect_source_locks(root)
    loaded = load_evaluation_config(
        root / "configs/evaluation/default.yaml",
        project_root=root,
    )
    pilot = expand_experiment_matrix(loaded, "pilot")
    pilot_design = loaded.experiments["pilot"].design
    if pilot_design is None:
        raise Gate3PreflightError("pilot experiment is missing its frozen design")
    available = set(os.environ) if environment_names is None else environment_names
    credential_name = authorization.credential.environment_variable
    checked_at = datetime.now(UTC) if now is None else now
    authorization_current = (
        checked_at.tzinfo is not None
        and checked_at.utcoffset() is not None
        and authorization.authorized_at is not None
        and authorization.expires_at is not None
        and authorization.authorized_at <= checked_at < authorization.expires_at
    )
    checks = (
        PreflightCheck(
            check_id="issue14-accepted",
            status=CheckStatus.PASSED if _accepted_issue14(root) else CheckStatus.FAILED,
            detail="Issue #14 offline evidence is accepted and contains no pilot outcomes",
        ),
        PreflightCheck(
            check_id="pilot-matrix-exact",
            status=(
                CheckStatus.PASSED
                if len(pilot.assignments) == 32
                and pilot.matrix_sha256 == actual_locks.pilot_matrix_sha256
                else CheckStatus.FAILED
            ),
            detail="pilot matrix must contain exactly 32 hash-bound assignments",
        ),
        PreflightCheck(
            check_id="source-locks-match",
            status=(
                CheckStatus.PASSED
                if authorization.source_locks == actual_locks
                else CheckStatus.FAILED
            ),
            detail="all Gate 1, Gate 2, Issue #14, dataset, prompt, metric and config hashes match",
        ),
        PreflightCheck(
            check_id="call-budget-amendment-applies",
            status=(
                CheckStatus.PASSED
                if _call_budget_amendment_applies(
                    call_budget_amendment,
                    configured_max_calls=pilot_design.limits.max_model_calls,
                    assignment_count=len(pilot.assignments),
                )
                else CheckStatus.FAILED
            ),
            detail=(
                "the outcome-blind 3,200-call amendment must match the frozen "
                "32 x 40 x two-stage pilot"
            ),
        ),
        PreflightCheck(
            check_id="authorization-approved",
            status=(
                CheckStatus.PASSED
                if authorization.decision is AuthorizationDecision.APPROVED
                else CheckStatus.BLOCKED
            ),
            detail="a named, time-bounded, pilot-only supervisor authorization is required",
        ),
        PreflightCheck(
            check_id="model-revision-resolved",
            status=CheckStatus.PASSED if authorization.model.resolved else CheckStatus.BLOCKED,
            detail=(
                "provider, model ID, immutable revision, license and adapter config are required"
            ),
        ),
        PreflightCheck(
            check_id="model-adapter-matches",
            status=(
                CheckStatus.PASSED
                if _model_adapter_ready(authorization, root)
                else CheckStatus.BLOCKED
            ),
            detail=(
                "adapter bytes, provider, model, revision, prompt and live-call flag must match"
            ),
        ),
        PreflightCheck(
            check_id="credential-present",
            status=(
                CheckStatus.PASSED
                if credential_name is not None and credential_name in available
                else CheckStatus.BLOCKED
            ),
            detail="only credential presence is checked; secret values are never persisted",
        ),
        PreflightCheck(
            check_id="budget-authorized",
            status=CheckStatus.PASSED if authorization.budget is not None else CheckStatus.BLOCKED,
            detail="hard call, input/output token, monetary and wall-clock limits are required",
        ),
        PreflightCheck(
            check_id="pilot-call-budget-feasible",
            status=(
                CheckStatus.PASSED
                if _pilot_call_budget_feasible(
                    authorization,
                    amendment=call_budget_amendment,
                    assignment_count=len(pilot.assignments),
                )
                else CheckStatus.BLOCKED
            ),
            detail=(
                "the complete authorization must reserve between 2,560 and 3,200 "
                "model calls under the approved pilot-only amendment"
            ),
        ),
        PreflightCheck(
            check_id="code-commit-matches",
            status=(
                CheckStatus.PASSED
                if authorization.code_commit_sha is not None
                and authorization.code_commit_sha == current_code_commit_sha
                else CheckStatus.BLOCKED
            ),
            detail="the executing checkout must match the supervisor-authorized commit",
        ),
        PreflightCheck(
            check_id="authorization-current",
            status=CheckStatus.PASSED if authorization_current else CheckStatus.BLOCKED,
            detail="the time-bounded Gate 3 authorization must be active at preflight",
        ),
        PreflightCheck(
            check_id="runtime-available",
            status=CheckStatus.PASSED if runtime_available else CheckStatus.BLOCKED,
            detail=(
                "the selected local or remote model transport must pass a no-output "
                "capability check"
            ),
        ),
    )
    blockers = tuple(check.detail for check in checks if check.status is not CheckStatus.PASSED)
    return Gate3PreflightResult.create(
        status="blocked" if blockers else "ready",
        authorization_sha256=sha256_value(authorization),
        source_locks=actual_locks,
        pilot_assignment_count=32,
        checks=checks,
        blockers=blockers,
    )


def build_blocked_evidence(preflight: Gate3PreflightResult) -> Gate3Evidence:
    if preflight.status != "blocked":
        raise Gate3PreflightError("blocked evidence requires a blocked preflight")
    acceptance = {
        "structured_outputs_validate": "blocked",
        "metrics_are_behavioral": "passed",
        "language_and_action_are_separate": "passed",
        "failures_are_quantified": "blocked",
        "all_factorial_cells_present": "blocked",
        "action_variance_present": "blocked",
        "condition_isolation_passes": "blocked",
        "safety_stops_absent": "passed",
        "live_calls_are_authorized": "blocked",
    }
    return Gate3Evidence.create(
        artifact_id="gate-3-evidence",
        task_id="gate-3-pilot",
        issue_number=27,
        gate_id="gate-3",
        path="artifacts/orchestration/gate-3.json",
        status="blocked",
        evidence_label="gate3_preflight_blocker_evidence",
        preflight_sha256=preflight.preflight_sha256,
        authorization_sha256=preflight.authorization_sha256,
        consumed_artifacts=(
            {
                "artifact_id": "issue-14-metric-spec",
                "path": "artifacts/evaluation/issue-14-metrics.json",
                "sha256": preflight.source_locks.issue14_artifact_sha256,
            },
        ),
        pilot_matrix_sha256=preflight.source_locks.pilot_matrix_sha256,
        integrity=PilotIntegritySummary(
            assigned_trajectories=32,
            started_trajectories=0,
            valid_trajectories=0,
            invalid_trajectories=0,
            missing_trajectories=0,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0,
            malformed_output_count=0,
            repaired_output_count=0,
        ),
        acceptance_tests=acceptance,
        blockers=preflight.blockers,
        pilot_executed=False,
        live_calls=0,
        paid_calls=0,
    )


def require_passed_gate3_evidence(path: Path) -> Gate3Evidence:
    try:
        evidence = Gate3Evidence.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise Gate3PreflightError(f"invalid Gate 3 evidence {path}: {exc}") from exc
    if evidence.status != "passed":
        raise Gate3PreflightError(f"Gate 3 is {evidence.status}; downstream execution is blocked")
    return evidence
