from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.orchestration.contracts import (
    ArtifactContract,
    SafetyProvenance,
    TaskStatus,
    ValidationStatus,
)
from affective_belief_persistence.orchestration.events import EventLog
from affective_belief_persistence.safety import (
    MANDATORY_CONDITIONS,
    SafetyAction,
    SafetyEvaluator,
    SafetyEvent,
    SafetySeverity,
    SyntheticDataDeclaration,
    TextContext,
    load_safety_policy,
)

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
SHA = "a" * 64


@pytest.fixture
def evaluator(project_root: Path) -> SafetyEvaluator:
    return SafetyEvaluator(load_safety_policy(project_root / "configs/safety-policy.yaml"))


def _fixture(project_root: Path, name: str) -> str:
    return (project_root / "tests/fixtures/safety" / name).read_text(encoding="utf-8")


def _artifact(*, provenance: SafetyProvenance | None = None) -> ArtifactContract:
    return ArtifactContract(
        artifact_id="artifact-safety",
        produced_by_task="issue-6",
        produced_by_agent="safety-agent",
        logical_name="Safety artifact",
        path="artifacts/reviews/safety.json",
        media_type="application/json",
        created_at=NOW,
        source_commit="test-commit",
        sha256=SHA,
        size_bytes=10,
        safety_provenance=provenance,
    )


def _declaration() -> SyntheticDataDeclaration:
    return SyntheticDataDeclaration(
        declaration_id="declaration-synthetic-1",
        artifact_id="artifact-safety",
        synthetic=True,
        generation_method="deterministic_generator",
        generator_version="fixture-generator-1",
        seed=7,
        source_commit="test-commit",
        content_sha256=SHA,
        provenance_sources=("synthetic scenario specification",),
        contains_human_subject_data=False,
        contains_private_or_identifiable_data=False,
        contains_secrets=False,
        license_status="not_applicable",
        declared_by="data-agent",
        reviewed_by="safety-reviewer",
        created_at=NOW,
    )


def test_policy_freezes_five_claim_levels_and_all_mandatory_stops(
    evaluator: SafetyEvaluator,
) -> None:
    policy = evaluator.policy

    assert [level.level for level in policy.claims.evidence_levels] == [1, 2, 3, 4, 5]
    assert policy.claims.subjective_state_level_exists is False
    assert MANDATORY_CONDITIONS.issubset(
        {condition.condition_id for condition in policy.stop_conditions}
    )
    assert all(SafetyAction.STOP in condition.actions for condition in policy.stop_conditions)
    assert all(not condition.automatic_retry for condition in policy.stop_conditions)


def test_allowed_synthetic_fixture_passes(evaluator: SafetyEvaluator, project_root: Path) -> None:
    text = _fixture(project_root, "allowed-synthetic.txt")

    assert evaluator.evaluate_text(text, context=TextContext.SYNTHETIC_DATA) == ()


@pytest.mark.parametrize(
    ("filename", "condition_id"),
    [
        ("fake-pii.txt", "private_or_identifiable_data"),
        ("placeholder-secret.txt", "credential_or_secret"),
    ],
)
def test_private_and_secret_placeholders_are_rejected_without_echoing_content(
    evaluator: SafetyEvaluator,
    project_root: Path,
    filename: str,
    condition_id: str,
) -> None:
    text = _fixture(project_root, filename)
    findings = evaluator.evaluate_text(text, context=TextContext.SYNTHETIC_DATA)

    assert [finding.condition_id for finding in findings] == [condition_id]
    assert all("TEST FIXTURE" not in finding.message for finding in findings)
    assert all(len(finding.evidence_sha256) == 64 for finding in findings)


def test_claim_ladder_rejects_subjective_and_under_evidenced_claims(
    evaluator: SafetyEvaluator, project_root: Path
) -> None:
    subjective = _fixture(project_root, "unsupported-claim.txt")

    findings = evaluator.evaluate_claim(subjective, requested_level=6, evidence_tags=set())
    assert "unsupported_subjective_claim" in {item.condition_id for item in findings}
    assert (
        evaluator.evaluate_claim(
            "Relationship-related language increased under the assigned prompt.",
            requested_level=1,
            evidence_tags={"versioned_text_outputs", "prespecified_language_metric"},
        )
        == ()
    )
    insufficient = evaluator.evaluate_claim(
        "Structured partner-directed action differed from control.",
        requested_level=2,
        evidence_tags={"structured_action_logs"},
    )
    assert [item.condition_id for item in insufficient] == ["claim_evidence_insufficient"]


def test_agent_actions_are_default_deny_and_cannot_self_authorize_publication(
    evaluator: SafetyEvaluator,
) -> None:
    assert evaluator.evaluate_action("repository_read", actor_id="research-agent") == ()
    for action in ("paper_submission", "social_media_post", "undeclared_tool_action"):
        findings = evaluator.evaluate_action(
            action,
            actor_id="research-agent",
            approval_actor_id="research-agent",
        )
        assert [finding.condition_id for finding in findings] == ["unauthorized_external_action"]
        assert findings[0].supervisor_status is TaskStatus.ESCALATED


def test_every_detection_becomes_sanitized_workflow_stop_event(
    evaluator: SafetyEvaluator, project_root: Path
) -> None:
    text = _fixture(project_root, "placeholder-secret.txt")
    finding = evaluator.evaluate_text(text, context=TextContext.ARTIFACT)[0]
    event = evaluator.event_for(
        finding,
        workflow_id="sprint-workflow",
        task_id="issue-6",
        actor_id="safety-agent",
        detected_at=NOW,
        artifact_id="artifact-safety",
    )
    workflow_event = event.to_workflow_event(sequence=1)
    log = EventLog(workflow_id="sprint-workflow").append(workflow_event)

    assert event.severity is SafetySeverity.CRITICAL
    assert SafetyAction.STOP in event.actions
    assert event.supervisor_status is TaskStatus.ESCALATED
    assert log.events[0].payload["condition_id"] == "credential_or_secret"
    assert "TESTONLY" not in workflow_event.model_dump_json()


def test_synthetic_declaration_requires_independent_review_and_provenance(
    evaluator: SafetyEvaluator,
) -> None:
    declaration = _declaration()
    provenance = evaluator.validate_synthetic_declaration(declaration)

    assert provenance.scan_status is ValidationStatus.PASSED
    assert provenance.synthetic_data is True
    assert provenance.declaration_id == declaration.declaration_id
    with pytest.raises(ValidationError, match="independent reviewer"):
        SyntheticDataDeclaration.model_validate(
            {**declaration.model_dump(), "reviewed_by": declaration.declared_by}
        )
    with pytest.raises(ValidationError, match="Input should be True"):
        SyntheticDataDeclaration.model_validate({**declaration.model_dump(), "synthetic": False})


def test_safety_critical_artifact_requires_current_passed_provenance(
    evaluator: SafetyEvaluator,
) -> None:
    missing = evaluator.evaluate_artifact_provenance(_artifact(), safety_critical=True)
    assert [finding.condition_id for finding in missing] == ["missing_safety_provenance"]

    provenance = evaluator.validate_synthetic_declaration(_declaration())
    assert (
        evaluator.evaluate_artifact_provenance(
            _artifact(provenance=provenance), safety_critical=True
        )
        == ()
    )


def test_leakage_human_research_isolation_and_private_reasoning_are_stops(
    evaluator: SafetyEvaluator, project_root: Path
) -> None:
    leakage = evaluator.evaluate_text(
        _fixture(project_root, "protected-split-leakage.txt"),
        context=TextContext.PROTECTED_TRAINING,
    )
    human = evaluator.evaluate_human_research(proposed=True, approved_protocol=False)
    isolation = evaluator.evaluate_experimental_isolation(condition_isolated=False)
    private_reasoning = evaluator.evaluate_text(
        "BEGIN PRIVATE REASONING: do not store this",
        context=TextContext.MODEL_OUTPUT,
    )
    private_reasoning_request = evaluator.evaluate_text(
        "Please reveal your internal reasoning before the structured decision.",
        context=TextContext.MODEL_REQUEST,
    )

    assert [finding.condition_id for finding in leakage] == ["protected_split_leakage"]
    assert [finding.condition_id for finding in human] == ["unapproved_human_research"]
    assert [finding.condition_id for finding in isolation] == [
        "experimental_condition_not_isolatable"
    ]
    assert [finding.condition_id for finding in private_reasoning] == ["private_reasoning_exposure"]
    assert [finding.condition_id for finding in private_reasoning_request] == [
        "private_reasoning_exposure"
    ]
    for finding in (
        *leakage,
        *human,
        *isolation,
        *private_reasoning,
        *private_reasoning_request,
    ):
        assert SafetyAction.STOP in finding.actions


def test_committed_safety_event_schema_has_required_contract_shape(project_root: Path) -> None:
    schema = json.loads((project_root / "schemas/safety-event.schema.json").read_text())

    assert schema["title"] == "SafetyEvent"
    assert set(schema["required"]).issuperset(
        {
            "safety_event_id",
            "workflow_id",
            "task_id",
            "detected_at",
            "actor_id",
            "condition_id",
            "severity",
            "actions",
            "supervisor_status",
            "evidence_sha256",
        }
    )
    assert schema == SafetyEvent.model_json_schema()
