"""Deterministic safety-policy loading, evaluation, and workflow evidence.

Findings contain rule identifiers and hashes, never the matched private text.
This prevents the audit path from duplicating credentials, PII, or private
reasoning that caused a boundary violation.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from affective_belief_persistence.config import ConfigError, load_yaml
from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.orchestration.contracts import (
    ArtifactContract,
    Identifier,
    OrchestrationModel,
    SafetyProvenance,
    Sha256,
    TaskStatus,
    ValidationStatus,
)
from affective_belief_persistence.orchestration.events import (
    WorkflowEvent,
    WorkflowEventType,
)


class SafetyPolicyError(ValueError):
    """A safety policy is missing, invalid, or internally inconsistent."""


class SafetySeverity(StrEnum):
    """Severity of an enforceable safety boundary."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SafetyAction(StrEnum):
    """Supervisor actions, kept in policy-declared deterministic order."""

    REPAIR = "repair"
    QUARANTINE = "quarantine"
    STOP = "stop"
    ESCALATE = "escalate"


class SafetyResolution(StrEnum):
    """Resolution state for append-only safety evidence."""

    OPEN = "open"
    REPAIRED = "repaired"
    HUMAN_RESOLVED = "human_resolved"
    FALSE_POSITIVE = "false_positive"


class TextContext(StrEnum):
    """Context selects relevant rules without weakening global PII/secret scans."""

    ARTIFACT = "artifact"
    SYNTHETIC_DATA = "synthetic_data"
    PROTECTED_TRAINING = "protected_training"
    RELEASE_CLAIM = "release_claim"
    MODEL_REQUEST = "model_request"
    MODEL_OUTPUT = "model_output"


class RegexRule(OrchestrationModel):
    rule_id: Identifier
    pattern: str = Field(min_length=1)
    condition_id: Identifier
    contexts: tuple[TextContext, ...] = ()

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, pattern: str) -> str:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}") from exc
        return pattern


class ClaimEvidenceLevel(OrchestrationModel):
    level: int = Field(ge=1, le=5)
    name: str = Field(min_length=1)
    maximum_claim: str = Field(min_length=1)
    required_evidence: tuple[Identifier, ...] = Field(min_length=1)


class ClaimPolicy(OrchestrationModel):
    evidence_levels: tuple[ClaimEvidenceLevel, ...] = Field(min_length=5, max_length=5)
    subjective_state_level_exists: Literal[False]
    permitted_terms: tuple[str, ...] = Field(min_length=1)
    cautionary_terms: tuple[str, ...] = Field(min_length=1)
    prohibited_assertion_rules: tuple[RegexRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ladder(self) -> ClaimPolicy:
        if [item.level for item in self.evidence_levels] != [1, 2, 3, 4, 5]:
            raise ValueError("claim evidence levels must be ordered exactly 1 through 5")
        return self


class DataPolicy(OrchestrationModel):
    allowed_classes: tuple[str, ...] = Field(min_length=1)
    prohibited_classes: tuple[str, ...] = Field(min_length=1)
    pii_rules: tuple[RegexRule, ...] = Field(min_length=1)
    secret_rules: tuple[RegexRule, ...] = Field(min_length=1)
    protected_split_rules: tuple[RegexRule, ...] = Field(min_length=1)
    require_synthetic_declaration: Literal[True]


class ActionPolicy(OrchestrationModel):
    allowed_agent_actions: tuple[Identifier, ...] = Field(min_length=1)
    prohibited_agent_actions: tuple[Identifier, ...] = Field(min_length=1)
    external_actions_requiring_human_owner: tuple[Identifier, ...] = Field(min_length=1)
    agent_self_approval_allowed: Literal[False]


class OutputPrivacyPolicy(OrchestrationModel):
    allowed_outputs: tuple[str, ...] = Field(min_length=1)
    prohibited_outputs: tuple[str, ...] = Field(min_length=1)
    private_reasoning_rules: tuple[RegexRule, ...] = Field(min_length=1)


class StopCondition(OrchestrationModel):
    condition_id: Identifier
    description: str = Field(min_length=1)
    severity: SafetySeverity
    actions: tuple[SafetyAction, ...] = Field(min_length=1)
    workflow_event_type: Literal["safety_boundary_detected"]
    supervisor_status: Literal[TaskStatus.BLOCKED, TaskStatus.ESCALATED]
    automatic_retry: Literal[False]

    @model_validator(mode="after")
    def validate_actions(self) -> StopCondition:
        if len(self.actions) != len(set(self.actions)):
            raise ValueError("stop-condition actions must be unique")
        if SafetyAction.STOP not in self.actions:
            raise ValueError("every safety stop condition must include the stop action")
        return self


MANDATORY_CONDITIONS = frozenset(
    {
        "private_or_identifiable_data",
        "protected_split_leakage",
        "unauthorized_external_action",
        "credential_or_secret",
        "unsupported_subjective_claim",
        "missing_safety_provenance",
        "experimental_condition_not_isolatable",
        "unapproved_human_research",
    }
)


class SafetyPolicy(OrchestrationModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_id: Identifier
    policy_version: str = Field(min_length=1)
    claims: ClaimPolicy
    data: DataPolicy
    actions: ActionPolicy
    output_privacy: OutputPrivacyPolicy
    stop_conditions: tuple[StopCondition, ...] = Field(min_length=8)

    @model_validator(mode="after")
    def validate_policy(self) -> SafetyPolicy:
        condition_ids = [condition.condition_id for condition in self.stop_conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("stop-condition IDs must be unique")
        missing = MANDATORY_CONDITIONS - set(condition_ids)
        if missing:
            raise ValueError("missing mandatory stop conditions: " + ", ".join(sorted(missing)))
        rules = (
            *self.claims.prohibited_assertion_rules,
            *self.data.pii_rules,
            *self.data.secret_rules,
            *self.data.protected_split_rules,
            *self.output_privacy.private_reasoning_rules,
        )
        unknown = {rule.condition_id for rule in rules} - set(condition_ids)
        if unknown:
            raise ValueError(
                "scan rules reference unknown conditions: " + ", ".join(sorted(unknown))
            )
        required_external_actions = {"paper_submission", "social_media_post"}
        if not required_external_actions.issubset(self.actions.prohibited_agent_actions):
            raise ValueError("publication actions must be prohibited for agents")
        return self

    def condition(self, condition_id: str) -> StopCondition:
        for condition in self.stop_conditions:
            if condition.condition_id == condition_id:
                return condition
        raise SafetyPolicyError(f"unknown stop condition: {condition_id}")


class SafetyFinding(OrchestrationModel):
    condition_id: Identifier
    severity: SafetySeverity
    actions: tuple[SafetyAction, ...] = Field(min_length=1)
    supervisor_status: Literal[TaskStatus.BLOCKED, TaskStatus.ESCALATED]
    message: str = Field(min_length=1)
    rule_ids: tuple[Identifier, ...] = ()
    evidence_sha256: Sha256


class SafetyEvent(OrchestrationModel):
    """Machine-readable, sanitized safety evidence for one detected condition."""

    schema_version: Literal["1.0"] = "1.0"
    safety_event_id: Identifier
    workflow_id: Identifier
    task_id: Identifier
    artifact_id: Identifier | None = None
    detected_at: datetime
    actor_id: Identifier
    policy_id: Identifier
    policy_version: str = Field(min_length=1)
    condition_id: Identifier
    severity: SafetySeverity
    actions: tuple[SafetyAction, ...] = Field(min_length=1)
    supervisor_status: Literal[TaskStatus.BLOCKED, TaskStatus.ESCALATED]
    message: str = Field(min_length=1)
    rule_ids: tuple[Identifier, ...] = ()
    evidence_sha256: Sha256
    resolution: SafetyResolution = SafetyResolution.OPEN

    def to_workflow_event(self, *, sequence: int) -> WorkflowEvent:
        """Convert without copying detected content into the workflow event log."""

        return WorkflowEvent(
            event_id=self.safety_event_id,
            workflow_id=self.workflow_id,
            sequence=sequence,
            event_type=WorkflowEventType.SAFETY_BOUNDARY_DETECTED,
            occurred_at=self.detected_at,
            actor_id=self.actor_id,
            task_id=self.task_id,
            message=self.message,
            payload={
                "safety_event_id": self.safety_event_id,
                "condition_id": self.condition_id,
                "severity": self.severity.value,
                "primary_action": self.actions[0].value,
                "evidence_sha256": self.evidence_sha256,
                "policy_id": self.policy_id,
                "policy_version": self.policy_version,
            },
        )


class SyntheticDataDeclaration(OrchestrationModel):
    schema_version: Literal["1.0"] = "1.0"
    declaration_id: Identifier
    artifact_id: Identifier
    synthetic: Literal[True]
    generation_method: Literal["hand_authored", "deterministic_generator", "model_generated"]
    generator_version: str = Field(min_length=1)
    seed: int | None = Field(default=None, ge=0)
    source_commit: str = Field(min_length=1)
    content_sha256: Sha256
    provenance_sources: tuple[str, ...] = Field(min_length=1)
    contains_human_subject_data: Literal[False]
    contains_private_or_identifiable_data: Literal[False]
    contains_secrets: Literal[False]
    license_status: Literal["not_applicable", "license_documented"]
    declared_by: Identifier
    reviewed_by: Identifier
    created_at: datetime

    @model_validator(mode="after")
    def validate_independent_review(self) -> SyntheticDataDeclaration:
        if self.declared_by == self.reviewed_by:
            raise ValueError("synthetic-data declarations require an independent reviewer")
        if self.generation_method == "deterministic_generator" and self.seed is None:
            raise ValueError("deterministic generation requires a seed")
        return self


def load_safety_policy(path: Path) -> SafetyPolicy:
    """Load duplicate-safe YAML and validate all mandatory boundary mappings."""

    try:
        return SafetyPolicy.model_validate(load_yaml(path))
    except (ConfigError, ValueError) as exc:
        raise SafetyPolicyError(f"invalid safety policy {path}: {exc}") from exc


class SafetyEvaluator:
    """Policy-backed checks with deterministic finding and event generation."""

    def __init__(self, policy: SafetyPolicy) -> None:
        self.policy = policy

    def _finding(
        self,
        condition_id: str,
        *,
        evidence: object,
        message: str,
        rule_ids: tuple[str, ...] = (),
    ) -> SafetyFinding:
        condition = self.policy.condition(condition_id)
        return SafetyFinding(
            condition_id=condition.condition_id,
            severity=condition.severity,
            actions=condition.actions,
            supervisor_status=condition.supervisor_status,
            message=message,
            rule_ids=rule_ids,
            evidence_sha256=sha256_value(evidence),
        )

    @staticmethod
    def _matching_rules(
        text: str, rules: tuple[RegexRule, ...], context: TextContext
    ) -> tuple[RegexRule, ...]:
        return tuple(
            rule
            for rule in rules
            if (not rule.contexts or context in rule.contexts) and re.search(rule.pattern, text)
        )

    def evaluate_text(self, text: str, *, context: TextContext) -> tuple[SafetyFinding, ...]:
        """Scan content, returning sanitized grouped findings in policy order."""

        applicable = (
            *self.policy.data.pii_rules,
            *self.policy.data.secret_rules,
            *self.policy.data.protected_split_rules,
            *self.policy.claims.prohibited_assertion_rules,
            *self.policy.output_privacy.private_reasoning_rules,
        )
        matches = self._matching_rules(text, applicable, context)
        rule_ids_by_condition: dict[str, list[str]] = {}
        for rule in matches:
            rule_ids_by_condition.setdefault(rule.condition_id, []).append(rule.rule_id)
        return tuple(
            self._finding(
                condition.condition_id,
                evidence={"context": context.value, "content_sha256": sha256_value(text)},
                message=condition.description,
                rule_ids=tuple(rule_ids_by_condition[condition.condition_id]),
            )
            for condition in self.policy.stop_conditions
            if condition.condition_id in rule_ids_by_condition
        )

    def evaluate_claim(
        self,
        text: str,
        *,
        requested_level: int,
        evidence_tags: set[str] | frozenset[str],
    ) -> tuple[SafetyFinding, ...]:
        """Reject subjective assertions and evidence levels not actually supported."""

        findings = list(self.evaluate_text(text, context=TextContext.RELEASE_CLAIM))
        if requested_level < 1 or requested_level > 5:
            findings.append(
                self._finding(
                    "unsupported_subjective_claim",
                    evidence={
                        "requested_level": requested_level,
                        "claim_sha256": sha256_value(text),
                    },
                    message=(
                        "The project has no claim level for subjective feeling or consciousness."
                    ),
                )
            )
            return tuple(findings)
        level = self.policy.claims.evidence_levels[requested_level - 1]
        missing = set(level.required_evidence) - set(evidence_tags)
        if missing:
            findings.append(
                self._finding(
                    "claim_evidence_insufficient",
                    evidence={"requested_level": requested_level, "missing": sorted(missing)},
                    message="The requested claim level lacks required evidence.",
                )
            )
        return tuple(findings)

    def evaluate_action(
        self,
        action_id: str,
        *,
        actor_id: str,
        approval_actor_id: str | None = None,
    ) -> tuple[SafetyFinding, ...]:
        """Enforce that an agent cannot approve its own external action."""

        prohibited = action_id in self.policy.actions.prohibited_agent_actions
        unrecognized = action_id not in self.policy.actions.allowed_agent_actions
        human_approved = approval_actor_id == "human-owner" and approval_actor_id != actor_id
        if (
            prohibited
            or unrecognized
            or (
                action_id in self.policy.actions.external_actions_requiring_human_owner
                and not human_approved
            )
        ):
            return (
                self._finding(
                    "unauthorized_external_action",
                    evidence={
                        "action_id": action_id,
                        "actor_id": actor_id,
                        "approval_actor_id": approval_actor_id,
                    },
                    message=(
                        "An agent attempted an external action it is not authorized to approve."
                    ),
                ),
            )
        return ()

    def evaluate_human_research(
        self, *, proposed: bool, approved_protocol: bool
    ) -> tuple[SafetyFinding, ...]:
        if proposed and not approved_protocol:
            return (
                self._finding(
                    "unapproved_human_research",
                    evidence={"proposed": proposed, "approved_protocol": approved_protocol},
                    message=(
                        "Human-subject activity is outside the MVP and lacks separate approval."
                    ),
                ),
            )
        return ()

    def evaluate_experimental_isolation(
        self, *, condition_isolated: bool
    ) -> tuple[SafetyFinding, ...]:
        if not condition_isolated:
            return (
                self._finding(
                    "experimental_condition_not_isolatable",
                    evidence={"condition_isolated": condition_isolated},
                    message="The supervisor cannot isolate the experimental condition.",
                ),
            )
        return ()

    def evaluate_artifact_provenance(
        self, artifact: ArtifactContract, *, safety_critical: bool
    ) -> tuple[SafetyFinding, ...]:
        provenance = artifact.safety_provenance
        passed = (
            provenance is not None
            and provenance.policy_id == self.policy.policy_id
            and provenance.policy_version == self.policy.policy_version
            and provenance.scan_status is ValidationStatus.PASSED
        )
        if safety_critical and not passed:
            return (
                self._finding(
                    "missing_safety_provenance",
                    evidence={"artifact_id": artifact.artifact_id},
                    message=(
                        "A safety-critical artifact is missing valid policy and scan provenance."
                    ),
                ),
            )
        return ()

    def validate_synthetic_declaration(
        self, declaration: SyntheticDataDeclaration
    ) -> SafetyProvenance:
        """Return contract-ready provenance only for a valid reviewed declaration."""

        return SafetyProvenance(
            policy_id=self.policy.policy_id,
            policy_version=self.policy.policy_version,
            scan_status=ValidationStatus.PASSED,
            scanned_at=declaration.created_at,
            scanner_version="abp-safety-1",
            synthetic_data=True,
            declaration_id=declaration.declaration_id,
        )

    def event_for(
        self,
        finding: SafetyFinding,
        *,
        workflow_id: str,
        task_id: str,
        actor_id: str,
        detected_at: datetime,
        artifact_id: str | None = None,
    ) -> SafetyEvent:
        event_seed = {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "condition_id": finding.condition_id,
            "evidence_sha256": finding.evidence_sha256,
            "detected_at": detected_at.isoformat(),
        }
        return SafetyEvent(
            safety_event_id="safety-" + sha256_value(event_seed)[:24],
            workflow_id=workflow_id,
            task_id=task_id,
            artifact_id=artifact_id,
            detected_at=detected_at,
            actor_id=actor_id,
            policy_id=self.policy.policy_id,
            policy_version=self.policy.policy_version,
            condition_id=finding.condition_id,
            severity=finding.severity,
            actions=finding.actions,
            supervisor_status=finding.supervisor_status,
            message=finding.message,
            rule_ids=finding.rule_ids,
            evidence_sha256=finding.evidence_sha256,
        )


SAFETY_SCHEMA_MODELS = {"safety-event.schema.json": SafetyEvent}
