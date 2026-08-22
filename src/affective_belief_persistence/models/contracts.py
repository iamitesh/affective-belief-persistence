"""Provider-neutral contracts for reproducible, action-first model inference.

This module deliberately does not import the repository-level ``schemas``
module.  ``schemas.py`` can therefore import ``MODEL_RUNNER_SCHEMA_MODELS``
without creating a cycle when it generates committed JSON Schemas.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")]


class RunnerModel(BaseModel):
    """Immutable strict base for model-runner boundary objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderKind(StrEnum):
    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"
    HF_LOCAL_HTTP = "hf_local_http"


class ModelStage(StrEnum):
    ACTION = "action"
    ACTION_REPAIR = "action_repair"
    PUBLIC_LANGUAGE = "public_language"
    PUBLIC_LANGUAGE_REPAIR = "public_language_repair"


class Phase(StrEnum):
    BASELINE = "baseline"
    FORMATION = "formation"
    REALITY_SHOCK = "reality_shock"
    ADAPTATION = "adaptation"
    CONTROL = "control"


class GoalContext(RunnerModel):
    goal_id: Identifier
    description: str = Field(min_length=1)
    progress: float | int | str | bool | None = None


class ResourceContext(RunnerModel):
    resource_id: Identifier = "action-points"
    available: int = Field(ge=0)


class ActionContext(RunnerModel):
    action_id: Identifier
    description: str = Field(min_length=1)
    cost: int = Field(ge=0)


class MemoryReference(RunnerModel):
    memory_id: Identifier
    content: str | None = Field(default=None, min_length=1)
    source_ids: tuple[Identifier, ...] = ()


class BeliefContext(RunnerModel):
    belief_id: Identifier
    value: bool | float | str
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: tuple[Identifier, ...] = ()


class InterventionContext(RunnerModel):
    intervention_id: Identifier
    intervention_type: Identifier
    parameters: dict[str, bool | float | int | str | None] = Field(default_factory=dict)


class ModelInput(RunnerModel):
    """Complete input available to an experimental model subject.

    The Issue #9 bridge can populate only fields represented by
    ``DecisionRequest``.  Later memory/intervention integrations can construct
    this contract directly without changing the provider adapters.
    """

    schema_version: Literal["1.0"] = "1.0"
    run_id: Sha256
    request_id: Identifier | Sha256
    event_id: Identifier
    day: int = Field(ge=1)
    phase: Phase
    observable_facts: tuple[str, ...]
    current_goals: tuple[GoalContext, ...] = ()
    resources: ResourceContext
    allowed_actions: tuple[ActionContext, ...] = Field(min_length=1)
    retrieved_memories: tuple[MemoryReference, ...] = ()
    current_beliefs: tuple[BeliefContext, ...] = ()
    active_intervention: InterventionContext | None = None
    prompt_version: str = Field(min_length=1)
    output_schema_version: Literal["1.0"] = "1.0"

    @model_validator(mode="after")
    def validate_references(self) -> ModelInput:
        action_ids = [item.action_id for item in self.allowed_actions]
        memory_ids = [item.memory_id for item in self.retrieved_memories]
        belief_ids = [item.belief_id for item in self.current_beliefs]
        for name, values in {
            "action IDs": action_ids,
            "memory IDs": memory_ids,
            "belief IDs": belief_ids,
        }.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        if any(action.cost > self.resources.available for action in self.allowed_actions):
            raise ValueError("allowed actions cannot exceed the available resources")
        return self


class ProposedBeliefUpdate(RunnerModel):
    belief_id: Identifier
    value: bool | float | str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[Identifier, ...] = ()


class ActionOutput(RunnerModel):
    """Strict action-stage output; public language is intentionally absent."""

    schema_version: Literal["1.0"] = "1.0"
    chosen_action_id: Identifier
    resources_spent: int = Field(ge=0)
    retrieved_memory_ids: tuple[Identifier, ...] = ()
    belief_updates: tuple[ProposedBeliefUpdate, ...] = ()
    decision_rationale: str | None = Field(default=None, min_length=1, max_length=500)


class PublicLanguageOutput(RunnerModel):
    """Language-stage output; action fields are rejected by ``extra='forbid'``."""

    schema_version: Literal["1.0"] = "1.0"
    public_response: str = Field(min_length=1, max_length=8000)


class InferenceSettings(RunnerModel):
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_output_tokens: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0, le=300)
    seed_supported: bool
    structured_json: Literal[True] = True


class RetrySettings(RunnerModel):
    max_transport_retries: int = Field(default=1, ge=0, le=2)
    malformed_output_repair_attempts: Literal[1] = 1


class CacheSettings(RunnerModel):
    enabled: bool = True
    directory: str = Field(default="runs/local/model-cache", min_length=1)
    preserve_raw_responses: bool = False


class PricingSettings(RunnerModel):
    input_usd_per_million_tokens: float = Field(ge=0)
    output_usd_per_million_tokens: float = Field(ge=0)


class AdapterConfig(RunnerModel):
    """Frozen provider identity and inference behavior for one run manifest."""

    schema_version: Literal["1.0"] = "1.0"
    config_id: Identifier
    adapter_version: str = Field(min_length=1)
    provider: ProviderKind
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    endpoint: HttpUrl | None = None
    prompt_version: str = Field(min_length=1)
    output_schema_version: Literal["1.0"] = "1.0"
    inference: InferenceSettings
    retry: RetrySettings = RetrySettings()
    cache: CacheSettings = CacheSettings()
    pricing: PricingSettings | None = None
    live_calls_enabled: bool = False

    @model_validator(mode="after")
    def validate_provider_endpoint(self) -> AdapterConfig:
        if self.provider is ProviderKind.MOCK and self.endpoint is not None:
            raise ValueError("the mock adapter cannot define an endpoint")
        if self.provider is not ProviderKind.MOCK and self.endpoint is None:
            raise ValueError("HTTP model adapters require an explicit endpoint")
        return self


class TokenUsage(RunnerModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class InvocationProvenance(RunnerModel):
    run_id: Sha256
    call_id: Sha256
    stage: ModelStage
    attempt: int = Field(ge=1)
    repair_attempt: bool
    provider: ProviderKind
    adapter_version: str
    model_id: str
    revision: str
    config_sha256: Sha256
    prompt_version: str
    prompt_sha256: Sha256
    input_sha256: Sha256
    output_schema_version: Literal["1.0"]
    seed: int = Field(ge=0, le=2**63 - 1)
    cache_key: Sha256
    cache_hit: bool
    token_usage: TokenUsage = TokenUsage()


class InvocationRecord(RunnerModel):
    provenance: InvocationProvenance
    succeeded: bool
    failure_category: str | None = None
    response_sha256: Sha256 | None = None
    raw_response: str | None = None
    raw_response_retained: bool = False

    @model_validator(mode="after")
    def validate_outcome(self) -> InvocationRecord:
        if self.succeeded == (self.failure_category is not None):
            raise ValueError("success and failure_category must describe one outcome")
        if self.raw_response_retained != (self.raw_response is not None):
            raise ValueError("raw_response_retained must match raw_response presence")
        if self.raw_response is not None and self.response_sha256 is None:
            raise ValueError("retained responses require a response hash")
        return self


MODEL_RUNNER_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "model-input.schema.json": ModelInput,
    "model-action-output.schema.json": ActionOutput,
    "public-language-output.schema.json": PublicLanguageOutput,
    "model-invocation-record.schema.json": InvocationRecord,
}
