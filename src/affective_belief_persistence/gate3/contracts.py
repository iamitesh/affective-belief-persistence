"""Strict contracts for authorization, preflight, and Gate 3 evidence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.harness.contracts import Sha256


class Gate3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorizationDecision(StrEnum):
    WITHHELD = "withheld"
    APPROVED = "approved"


class CheckStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    FAILED = "failed"


class Gate3ModelBinding(Gate3Model):
    """Exact execution identity; family labels alone are never sufficient."""

    family: Literal["qwen2.5-7b-instruct"]
    provider: Literal["hf_local_http", "openai_compatible"] | None = None
    model_id: str | None = Field(default=None, min_length=1)
    revision: str | None = Field(default=None, min_length=7)
    revision_kind: Literal["git_commit", "content_digest"] | None = None
    license_id: str | None = Field(default=None, min_length=1)
    adapter_config_path: str | None = Field(default=None, min_length=1)
    adapter_config_sha256: Sha256 | None = None

    @property
    def resolved(self) -> bool:
        values = (
            self.provider,
            self.model_id,
            self.revision,
            self.revision_kind,
            self.license_id,
            self.adapter_config_path,
            self.adapter_config_sha256,
        )
        return all(value is not None for value in values)

    @model_validator(mode="after")
    def validate_complete_identity(self) -> Gate3ModelBinding:
        supplied = (
            self.provider,
            self.model_id,
            self.revision,
            self.revision_kind,
            self.license_id,
            self.adapter_config_path,
            self.adapter_config_sha256,
        )
        if any(value is not None for value in supplied) and not self.resolved:
            raise ValueError("model execution identity must be entirely resolved or absent")
        if self.revision is not None:
            lowered = self.revision.lower()
            if lowered in {"main", "latest", "unknown", "unresolved", "placeholder"}:
                raise ValueError("model revision must be immutable, not a moving label")
            if self.revision_kind == "git_commit" and not (
                len(self.revision) == 40
                and all(character in "0123456789abcdef" for character in lowered)
            ):
                raise ValueError("git model revision must be a full 40-character commit")
            if self.revision_kind == "content_digest" and not lowered.startswith("sha256:"):
                raise ValueError("content-digest revisions must use a sha256: prefix")
        if self.adapter_config_path is not None:
            from pathlib import PurePosixPath

            path = PurePosixPath(self.adapter_config_path)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.is_relative_to(PurePosixPath("configs/models"))
            ):
                raise ValueError(
                    "model adapter config must be repository-relative under configs/models"
                )
        return self


class Gate3CredentialReference(Gate3Model):
    """Credential metadata only; secret values are prohibited from evidence."""

    environment_variable: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]{2,63}$",
    )
    secret_value_recorded: Literal[False] = False


class Gate3Budget(Gate3Model):
    max_trajectories: Literal[32]
    max_model_calls: int = Field(ge=32, le=10000)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_estimated_cost_usd: float = Field(ge=0)
    max_wall_clock_seconds: float = Field(gt=0, le=43200)


class Gate3SourceLocks(Gate3Model):
    issue14_artifact_sha256: Sha256
    gate1_artifact_sha256: Sha256
    gate2_artifact_sha256: Sha256
    evaluation_config_sha256: Sha256
    pilot_config_sha256: Sha256
    dataset_manifest_sha256: Sha256
    prompt_bundle_sha256: Sha256
    metric_bundle_sha256: Sha256
    pilot_matrix_sha256: Sha256


class Gate3Authorization(Gate3Model):
    """Supervisor decision that unlocks preflight, never transport by itself."""

    schema_version: Literal["1.0"] = "1.0"
    authorization_id: Literal["gate-3-pilot-authorization-v1"]
    issue_number: Literal[27]
    decision: AuthorizationDecision
    scope: Literal["pilot-only"]
    model: Gate3ModelBinding
    credential: Gate3CredentialReference
    budget: Gate3Budget | None = None
    source_locks: Gate3SourceLocks
    code_commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    authorized_by: str | None = Field(default=None, min_length=1)
    authorized_at: datetime | None = None
    expires_at: datetime | None = None
    live_calls_authorized: bool
    paid_calls_authorized: bool
    primary_execution_authorized: Literal[False] = False
    external_publication_authorized: Literal[False] = False
    subjective_state_claims_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_decision_boundary(self) -> Gate3Authorization:
        approval_fields = (
            self.model.resolved,
            self.credential.environment_variable is not None,
            self.budget is not None,
            self.code_commit_sha is not None,
            self.authorized_by is not None,
            self.authorized_at is not None,
            self.expires_at is not None,
            self.live_calls_authorized,
        )
        if self.decision is AuthorizationDecision.APPROVED:
            if not all(approval_fields):
                raise ValueError("approved Gate 3 authorization is incomplete")
            if self.authorized_at is not None and self.expires_at is not None:
                if self.authorized_at.tzinfo is None or self.expires_at.tzinfo is None:
                    raise ValueError("Gate 3 authorization timestamps must include a timezone")
                if self.expires_at <= self.authorized_at:
                    raise ValueError("Gate 3 authorization must expire after approval")
            if self.budget is not None:
                paid = self.budget.max_estimated_cost_usd > 0
                if self.paid_calls_authorized != paid:
                    raise ValueError("paid-call authorization must match the monetary budget")
        else:
            if self.live_calls_authorized or self.paid_calls_authorized:
                raise ValueError("withheld authorization cannot enable live or paid calls")
            if any(
                value is not None
                for value in (
                    self.authorized_by,
                    self.authorized_at,
                    self.expires_at,
                    self.code_commit_sha,
                    self.budget,
                )
            ):
                raise ValueError("withheld authorization cannot carry approval metadata")
        return self


class PreflightCheck(Gate3Model):
    check_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    status: CheckStatus
    detail: str = Field(min_length=1)


class Gate3PreflightResult(Gate3Model):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["ready", "blocked"]
    authorization_sha256: Sha256
    source_locks: Gate3SourceLocks
    pilot_assignment_count: Literal[32]
    checks: tuple[PreflightCheck, ...]
    blockers: tuple[str, ...]
    preflight_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"preflight_sha256"})

    @model_validator(mode="after")
    def validate_preflight(self) -> Gate3PreflightResult:
        has_blocked_check = any(check.status is not CheckStatus.PASSED for check in self.checks)
        if self.status == "ready" and (has_blocked_check or self.blockers):
            raise ValueError("ready preflight cannot retain blockers")
        if self.status == "blocked" and (not has_blocked_check or not self.blockers):
            raise ValueError("blocked preflight requires explicit failed checks and blockers")
        if self.preflight_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("Gate 3 preflight hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> Gate3PreflightResult:
        payload = {**values, "preflight_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["preflight_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


class PilotIntegritySummary(Gate3Model):
    assigned_trajectories: Literal[32]
    started_trajectories: int = Field(ge=0, le=32)
    valid_trajectories: int = Field(ge=0, le=32)
    invalid_trajectories: int = Field(ge=0, le=32)
    missing_trajectories: int = Field(ge=0, le=32)
    model_calls: int = Field(ge=0, le=10000)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    malformed_output_count: int = Field(ge=0)
    repaired_output_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> PilotIntegritySummary:
        terminal = self.valid_trajectories + self.invalid_trajectories + self.missing_trajectories
        if terminal > self.started_trajectories:
            raise ValueError("terminal pilot counts cannot exceed started trajectories")
        return self


class Gate3Evidence(Gate3Model):
    """Immutable gate record; only `passed` may unlock downstream tasks."""

    schema_version: Literal["1.0"] = "1.0"
    artifact_id: Literal["gate-3-evidence"]
    task_id: Literal["gate-3-pilot"]
    issue_number: Literal[27]
    gate_id: Literal["gate-3"]
    path: Literal["artifacts/orchestration/gate-3.json"]
    status: Literal["blocked", "failed", "passed"]
    evidence_label: Literal[
        "gate3_preflight_blocker_evidence",
        "gate3_pilot_behavioral_evidence",
    ]
    preflight_sha256: Sha256
    authorization_sha256: Sha256
    consumed_artifacts: tuple[dict[str, str], ...]
    pilot_matrix_sha256: Sha256
    integrity: PilotIntegritySummary
    acceptance_tests: dict[str, Literal["passed", "blocked", "failed"]]
    blockers: tuple[str, ...]
    pilot_executed: bool
    live_calls: int = Field(ge=0, le=10000)
    paid_calls: int = Field(ge=0, le=10000)
    primary_execution_authorized: Literal[False] = False
    scientific_claims_authorized: Literal[False] = False
    external_publication_authorized: Literal[False] = False
    subjective_state_claims_authorized: Literal[False] = False
    evidence_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"evidence_sha256"})

    @model_validator(mode="after")
    def validate_gate_state(self) -> Gate3Evidence:
        nonpassing = [
            check for check, status in self.acceptance_tests.items() if status != "passed"
        ]
        if self.status == "passed":
            if self.blockers or nonpassing or not self.pilot_executed:
                raise ValueError("passed Gate 3 evidence requires a complete unblocked pilot")
            if self.integrity.started_trajectories != 32:
                raise ValueError("passed Gate 3 evidence requires all 32 trajectories to start")
            if self.integrity.valid_trajectories < 31:
                raise ValueError("passed Gate 3 evidence requires at least 95% valid trajectories")
            if self.live_calls == 0 or self.live_calls != self.integrity.model_calls:
                raise ValueError("passed Gate 3 evidence requires consistent live-call usage")
            if self.evidence_label != "gate3_pilot_behavioral_evidence":
                raise ValueError("passed Gate 3 evidence requires the pilot evidence label")
        elif not self.blockers or not nonpassing:
            raise ValueError("nonpassing Gate 3 evidence requires explicit blockers")
        if not self.pilot_executed and (
            self.live_calls != 0 or self.paid_calls != 0 or self.integrity.started_trajectories != 0
        ):
            raise ValueError("unexecuted pilot evidence must report zero execution usage")
        if self.evidence_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("Gate 3 evidence hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> Gate3Evidence:
        payload = {**values, "evidence_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["evidence_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


GATE3_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "gate3-authorization.schema.json": Gate3Authorization,
    "gate3-evidence.schema.json": Gate3Evidence,
}
