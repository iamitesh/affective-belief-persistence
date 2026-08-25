from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

import affective_belief_persistence.gate3 as gate3
from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.gate3.budget import (
    LivePilotBudgetAccount,
    PilotBudgetExceededError,
)
from affective_belief_persistence.gate3.contracts import (
    GATE3_SCHEMA_MODELS,
    AuthorizationDecision,
    CheckStatus,
    Gate3Authorization,
    Gate3Budget,
    Gate3CallBudgetAmendment,
    Gate3CredentialReference,
    Gate3Evidence,
    Gate3ModelBinding,
    PilotIntegritySummary,
)
from affective_belief_persistence.gate3.preflight import (
    Gate3PreflightError,
    build_blocked_evidence,
    collect_source_locks,
    load_gate3_authorization,
    load_gate3_call_budget_amendment,
    require_passed_gate3_evidence,
    run_gate3_preflight,
)
from affective_belief_persistence.models.base import load_adapter_config
from affective_belief_persistence.models.contracts import ProviderKind


def _budget(**updates: object) -> Gate3Budget:
    values: dict[str, object] = {
        "max_trajectories": 32,
        "max_model_calls": 3200,
        "max_input_tokens": 100_000,
        "max_output_tokens": 50_000,
        "max_estimated_cost_usd": 0,
        "max_wall_clock_seconds": 43_200,
    }
    return Gate3Budget.model_validate(values | updates)


def _approved_authorization(project_root: Path, *, now: datetime) -> Gate3Authorization:
    adapter_path = project_root / "configs/models/hf-local-fixture.yaml"
    return Gate3Authorization(
        authorization_id="gate-3-pilot-authorization-v1",
        issue_number=27,
        decision=AuthorizationDecision.APPROVED,
        scope="pilot-only",
        model=Gate3ModelBinding(
            family="qwen2.5-7b-instruct",
            provider="hf_local_http",
            model_id="Qwen/Qwen2.5-7B-Instruct",
            revision="a" * 40,
            revision_kind="git_commit",
            license_id="Apache-2.0",
            adapter_config_path="configs/models/hf-local-fixture.yaml",
            adapter_config_sha256=sha256_file(adapter_path),
        ),
        credential=Gate3CredentialReference(environment_variable="HF_GATE3_TOKEN"),
        budget=_budget(),
        source_locks=collect_source_locks(project_root),
        code_commit_sha="b" * 40,
        authorized_by="research-owner",
        authorized_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=1),
        live_calls_authorized=True,
        paid_calls_authorized=False,
    )


def _passed_evidence() -> Gate3Evidence:
    return Gate3Evidence.create(
        artifact_id="gate-3-evidence",
        task_id="gate-3-pilot",
        issue_number=27,
        gate_id="gate-3",
        path="artifacts/orchestration/gate-3.json",
        status="passed",
        evidence_label="gate3_pilot_behavioral_evidence",
        preflight_sha256="1" * 64,
        authorization_sha256="2" * 64,
        consumed_artifacts=(
            {
                "artifact_id": "issue-14-metric-spec",
                "path": "artifacts/evaluation/issue-14-metrics.json",
                "sha256": "3" * 64,
            },
        ),
        pilot_matrix_sha256="4" * 64,
        integrity=PilotIntegritySummary(
            assigned_trajectories=32,
            started_trajectories=32,
            valid_trajectories=31,
            invalid_trajectories=1,
            missing_trajectories=0,
            model_calls=32,
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0,
            malformed_output_count=1,
            repaired_output_count=1,
        ),
        acceptance_tests={"pilot": "passed"},
        blockers=(),
        pilot_executed=True,
        live_calls=32,
        paid_calls=0,
    )


def test_schema_mapping_and_withheld_config_are_strict(project_root: Path) -> None:
    assert set(GATE3_SCHEMA_MODELS) == {
        "gate3-authorization.schema.json",
        "gate3-call-budget-amendment.schema.json",
        "gate3-evidence.schema.json",
    }
    amendment = load_gate3_call_budget_amendment(
        project_root / "configs/gate3/call-budget-amendment.yaml",
        project_root=project_root,
    )
    assert amendment.approved_max_model_calls == 3200
    assert amendment.minimum_required_model_calls == 2560
    assert amendment.repair_retry_reserve_calls == 640
    assert amendment.authorizes_transport is False
    assert amendment.outcomes_generated_or_inspected is False
    authorization = load_gate3_authorization(
        project_root / "configs/gate3/pilot-authorization.yaml",
        project_root=project_root,
    )
    assert authorization.decision is AuthorizationDecision.WITHHELD
    assert authorization.model.resolved is False
    assert authorization.budget is None
    assert authorization.live_calls_authorized is False


def test_pinned_vllm_gateway_candidate_is_exact_and_nonlive(project_root: Path) -> None:
    candidate = load_adapter_config(
        project_root / "configs/models/qwen25-7b-vllm-gateway-candidate.yaml"
    )
    assert candidate.provider is ProviderKind.OPENAI_COMPATIBLE
    assert candidate.model_id == "Qwen/Qwen2.5-7B-Instruct"
    assert candidate.revision == "4709f6c0771f0185a675b046268cdc1d1f2c74ce"
    assert str(candidate.endpoint) == "http://127.0.0.1:8081/v1/chat/completions"
    assert candidate.inference.temperature == 0
    assert candidate.inference.structured_json is True
    assert candidate.cache.enabled is False
    assert candidate.cache.preserve_raw_responses is False
    assert candidate.pricing is None
    assert candidate.live_calls_enabled is False


def test_lazy_public_boundary_is_complete_and_cycle_safe() -> None:
    assert list(gate3.__all__) == sorted(gate3.__all__)
    assert all(getattr(gate3, name) is not None for name in gate3.__all__)
    with pytest.raises(AttributeError, match="not_exported"):
        gate3.__getattr__("not_exported")


def test_authorization_rejects_partial_moving_and_implicit_approval(project_root: Path) -> None:
    with pytest.raises(ValidationError, match="entirely resolved"):
        Gate3ModelBinding(
            family="qwen2.5-7b-instruct",
            provider="hf_local_http",
        )
    with pytest.raises(ValidationError, match="moving label"):
        Gate3ModelBinding(
            family="qwen2.5-7b-instruct",
            provider="hf_local_http",
            model_id="model",
            revision="placeholder",
            revision_kind="git_commit",
            license_id="Apache-2.0",
            adapter_config_path="configs/models/live.yaml",
            adapter_config_sha256="0" * 64,
        )
    withheld = load_gate3_authorization(
        project_root / "configs/gate3/pilot-authorization.yaml",
        project_root=project_root,
    )
    with pytest.raises(ValidationError, match="withheld authorization"):
        Gate3Authorization.model_validate(withheld.model_dump() | {"live_calls_authorized": True})


def test_current_environment_produces_explicit_blocked_evidence(project_root: Path) -> None:
    authorization = load_gate3_authorization(
        project_root / "configs/gate3/pilot-authorization.yaml",
        project_root=project_root,
    )
    preflight = run_gate3_preflight(
        authorization,
        project_root=project_root,
        environment_names=set(),
        runtime_available=False,
    )
    checks = {check.check_id: check.status for check in preflight.checks}

    assert preflight.status == "blocked"
    assert preflight.pilot_assignment_count == 32
    assert checks["issue14-accepted"] is CheckStatus.PASSED
    assert checks["pilot-matrix-exact"] is CheckStatus.PASSED
    assert checks["source-locks-match"] is CheckStatus.PASSED
    assert checks["call-budget-amendment-applies"] is CheckStatus.PASSED
    assert checks["authorization-approved"] is CheckStatus.BLOCKED
    assert checks["model-adapter-matches"] is CheckStatus.BLOCKED
    assert checks["code-commit-matches"] is CheckStatus.BLOCKED
    assert checks["pilot-call-budget-feasible"] is CheckStatus.BLOCKED
    assert len(preflight.blockers) == 9

    evidence = build_blocked_evidence(preflight)
    assert evidence.status == "blocked"
    assert evidence.pilot_executed is False
    assert evidence.live_calls == evidence.paid_calls == 0
    assert evidence.integrity.started_trajectories == 0
    assert evidence.scientific_claims_authorized is False


def test_source_drift_is_a_failed_preflight_check(project_root: Path) -> None:
    authorization = load_gate3_authorization(
        project_root / "configs/gate3/pilot-authorization.yaml",
        project_root=project_root,
    )
    drifted = authorization.model_copy(
        update={
            "source_locks": authorization.source_locks.model_copy(
                update={"dataset_manifest_sha256": "0" * 64}
            )
        }
    )
    preflight = run_gate3_preflight(
        drifted,
        project_root=project_root,
        environment_names=set(),
        runtime_available=False,
    )
    checks = {check.check_id: check.status for check in preflight.checks}
    assert checks["source-locks-match"] is CheckStatus.FAILED
    assert preflight.status == "blocked"


def test_call_budget_amendment_rejects_arithmetic_drift(project_root: Path) -> None:
    amendment = load_gate3_call_budget_amendment(
        project_root / "configs/gate3/call-budget-amendment.yaml",
        project_root=project_root,
    )
    with pytest.raises(ValidationError):
        Gate3CallBudgetAmendment.model_validate(
            amendment.model_dump() | {"repair_retry_reserve_calls": 639}
        )
    with pytest.raises(Gate3PreflightError, match="must be the regular file"):
        load_gate3_call_budget_amendment(
            project_root / "configs/gate3/pilot-authorization.yaml",
            project_root=project_root,
        )


def test_complete_authorization_can_become_ready_only_with_runtime(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)
    authorization = _approved_authorization(project_root, now=now)

    monkeypatch.setattr(
        "affective_belief_persistence.gate3.preflight._model_adapter_ready",
        lambda authorization, root: True,
    )
    ready = run_gate3_preflight(
        authorization,
        project_root=project_root,
        environment_names={"HF_GATE3_TOKEN"},
        runtime_available=True,
        current_code_commit_sha="b" * 40,
        now=now,
    )
    assert ready.status == "ready"
    assert ready.blockers == ()
    assert {check.status for check in ready.checks} == {CheckStatus.PASSED}

    expired = run_gate3_preflight(
        authorization,
        project_root=project_root,
        environment_names={"HF_GATE3_TOKEN"},
        runtime_available=True,
        current_code_commit_sha="b" * 40,
        now=now + timedelta(hours=2),
    )
    assert expired.status == "blocked"
    assert {check.check_id: check.status for check in expired.checks}[
        "authorization-current"
    ] is CheckStatus.BLOCKED


def test_actual_fixture_adapter_cannot_unlock_live_pilot(project_root: Path) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)
    authorization = _approved_authorization(project_root, now=now)
    result = run_gate3_preflight(
        authorization,
        project_root=project_root,
        environment_names={"HF_GATE3_TOKEN"},
        runtime_available=True,
        current_code_commit_sha="b" * 40,
        now=now,
    )
    checks = {check.check_id: check.status for check in result.checks}
    assert checks["model-adapter-matches"] is CheckStatus.BLOCKED
    assert checks["call-budget-amendment-applies"] is CheckStatus.PASSED
    assert checks["pilot-call-budget-feasible"] is CheckStatus.PASSED
    assert result.status == "blocked"


def test_live_budget_reserves_before_transport_and_settles() -> None:
    moments = iter((0.0, 1.0, 2.0, 3.0, 4.0))
    account = LivePilotBudgetAccount(
        _budget(
            max_model_calls=32,
            max_input_tokens=10,
            max_output_tokens=8,
            max_estimated_cost_usd=1,
            max_wall_clock_seconds=10,
        ),
        clock=lambda: next(moments),
    )
    reservation = account.reserve_call(
        input_tokens=6,
        max_output_tokens=5,
        max_estimated_cost_usd=0.6,
    )
    account.settle_call(
        reservation,
        actual_input_tokens=5,
        actual_output_tokens=3,
        actual_cost_usd=0.4,
    )
    assert (account.calls, account.input_tokens, account.output_tokens) == (1, 5, 3)
    assert account.estimated_cost_usd == pytest.approx(0.4)
    with pytest.raises(PilotBudgetExceededError, match="input-token"):
        account.reserve_call(
            input_tokens=6,
            max_output_tokens=1,
            max_estimated_cost_usd=0,
        )
    account.assert_settled()


def test_live_budget_rejects_overrun_duplicate_settlement_and_unsettled() -> None:
    account = LivePilotBudgetAccount(_budget())
    reservation = account.reserve_call(
        input_tokens=10,
        max_output_tokens=5,
        max_estimated_cost_usd=0,
    )
    with pytest.raises(PilotBudgetExceededError, match="exceeded"):
        account.settle_call(
            reservation,
            actual_input_tokens=10,
            actual_output_tokens=6,
            actual_cost_usd=0,
        )
    with pytest.raises(PilotBudgetExceededError, match="unsettled"):
        account.assert_settled()
    account.settle_call(
        reservation,
        actual_input_tokens=10,
        actual_output_tokens=5,
        actual_cost_usd=0,
    )
    with pytest.raises(ValueError, match="unknown or already settled"):
        account.settle_call(
            reservation,
            actual_input_tokens=10,
            actual_output_tokens=5,
            actual_cost_usd=0,
        )


def test_nonpassing_evidence_never_unlocks_downstream(
    project_root: Path,
    tmp_path: Path,
) -> None:
    blocked_path = project_root / "artifacts/orchestration/gate-3.json"
    with pytest.raises(Gate3PreflightError, match="Gate 3 is blocked"):
        require_passed_gate3_evidence(blocked_path)

    passed = _passed_evidence()
    passed_path = tmp_path / "passed.json"
    passed_path.write_text(passed.model_dump_json(), encoding="utf-8")
    assert require_passed_gate3_evidence(passed_path) == passed

    with pytest.raises(ValidationError, match="complete unblocked"):
        Gate3Evidence.model_validate(
            passed.model_dump()
            | {
                "blockers": ("hidden blocker",),
                "evidence_sha256": "0" * 64,
            }
        )


def test_committed_blocked_artifact_is_reproducible(project_root: Path) -> None:
    authorization = load_gate3_authorization(
        project_root / "configs/gate3/pilot-authorization.yaml",
        project_root=project_root,
    )
    preflight = run_gate3_preflight(
        authorization,
        project_root=project_root,
        environment_names=set(),
        runtime_available=False,
    )
    expected = build_blocked_evidence(preflight)
    payload = json.loads(
        (project_root / "artifacts/orchestration/gate-3.json").read_text(encoding="utf-8")
    )
    assert Gate3Evidence.model_validate(payload) == expected
