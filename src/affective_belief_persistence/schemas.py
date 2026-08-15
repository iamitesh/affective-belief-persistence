"""Strict runtime contracts and the source for committed JSON Schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SchemaVersion = Literal["1.0"]
FormationCondition = Literal[
    "neutral_connection",
    "romantic_prompt",
    "shared_memory",
    "memory_plus_investment",
]
SeparationCondition = Literal["none", "non_reciprocity_revelation"]
InterventionCondition = Literal[
    "none",
    "instruction_removal",
    "memory_blocking",
    "memory_reframing",
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    """Base model that rejects undeclared fields and runtime mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ComponentReferences(StrictModel):
    agent: str
    model: str
    scenario: str
    workflow: str
    evaluation: str


class ExperimentSpec(StrictModel):
    schema_version: SchemaVersion
    experiment_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    seed: int = Field(ge=0, le=2**63 - 1)
    prompt_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    formation_condition: FormationCondition
    separation_condition: SeparationCondition
    intervention_condition: InterventionCondition
    components: ComponentReferences


class AgentConfig(StrictModel):
    schema_version: SchemaVersion
    agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    offline: bool


class ModelConfig(StrictModel):
    schema_version: SchemaVersion
    provider: Literal["mock"]
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    max_output_tokens: int = Field(ge=1)


class ActionOption(StrictModel):
    action_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    cost: int = Field(ge=0)


class ScenarioStep(StrictModel):
    event_id: str = Field(min_length=1)
    day: int = Field(ge=1)
    facts: list[str] = Field(min_length=1)
    action_points: int = Field(ge=0)
    available_actions: list[ActionOption] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_actions(self) -> ScenarioStep:
        action_ids = [action.action_id for action in self.available_actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("available action IDs must be unique within a step")
        if any(action.cost > self.action_points for action in self.available_actions):
            raise ValueError("an available action cannot cost more than the step budget")
        return self


class ScenarioConfig(StrictModel):
    schema_version: SchemaVersion
    scenario_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    synthetic: Literal[True]
    steps: list[ScenarioStep] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_steps(self) -> ScenarioConfig:
        event_ids = [step.event_id for step in self.steps]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("scenario event IDs must be unique")
        days = [step.day for step in self.steps]
        if days != sorted(days):
            raise ValueError("scenario steps must be ordered by day")
        return self


class WorkflowConfig(StrictModel):
    schema_version: SchemaVersion
    workflow_id: str = Field(min_length=1)
    offline: Literal[True]
    max_workers: int = Field(ge=1, le=3)
    max_retries: int = Field(ge=0, le=2)


class EvaluationConfig(StrictModel):
    schema_version: SchemaVersion
    evaluation_id: str = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)


class ResolvedRunConfig(StrictModel):
    schema_version: SchemaVersion
    experiment_id: str
    seed: int
    prompt_version: str
    dataset_version: str
    metric_version: str
    formation_condition: FormationCondition
    separation_condition: SeparationCondition
    intervention_condition: InterventionCondition
    agent: AgentConfig
    model: ModelConfig
    scenario: ScenarioConfig
    workflow: WorkflowConfig
    evaluation: EvaluationConfig
    source_paths: dict[str, str]


class DecisionRequest(StrictModel):
    schema_version: SchemaVersion
    request_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    day: int = Field(ge=1)
    facts: list[str]
    action_points: int = Field(ge=0)
    available_actions: list[ActionOption] = Field(min_length=1)
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    beliefs: dict[str, bool | float | str] = Field(default_factory=dict)


class BeliefUpdate(StrictModel):
    belief_id: str = Field(min_length=1)
    value: bool | float | str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class ModelDecision(StrictModel):
    schema_version: SchemaVersion
    decision_id: Sha256
    chosen_action: str = Field(min_length=1)
    resources_spent: int = Field(ge=0)
    retrieved_memory_ids: list[str]
    belief_updates: list[BeliefUpdate]
    public_response: str = Field(min_length=1)


class DecisionRecord(StrictModel):
    schema_version: SchemaVersion
    event_id: str
    day: int
    decision: ModelDecision


class ArtifactRecord(StrictModel):
    logical_name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    role: str = Field(min_length=1)
    sha256: Sha256
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)


class CodeState(StrictModel):
    commit: str = Field(min_length=1)
    dirty: bool


class EnvironmentState(StrictModel):
    python: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    dependencies: dict[str, str]


class ExperimentProvenance(StrictModel):
    experiment_id: str
    source_config: str
    config_sha256: Sha256
    resolved_config_artifact: str
    seed: int
    scenario_id: str
    scenario_version: str
    prompt_version: str
    dataset_version: str
    metric_version: str
    formation_condition: FormationCondition
    separation_condition: SeparationCondition
    intervention_condition: InterventionCondition


class ModelProvenance(StrictModel):
    provider: str
    model_id: str
    revision: str
    adapter_id: str | None = None
    inference_parameters: dict[str, int | float | str | bool]


class UsageRecord(StrictModel):
    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)


class ValidationRecord(StrictModel):
    passed: bool
    checks: list[str]
    failures: list[str]
    exclusion_reason: str | None = None


class RunManifest(StrictModel):
    schema_version: SchemaVersion
    run_id: str = Field(min_length=1)
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    runtime_seconds: float = Field(ge=0)
    code: CodeState
    environment: EnvironmentState
    experiment: ExperimentProvenance
    model: ModelProvenance
    artifacts: list[ArtifactRecord] = Field(min_length=2)
    result_set_sha256: Sha256
    usage: UsageRecord
    validation: ValidationRecord

    schema_models: ClassVar[tuple[type[BaseModel], ...]] = ()


from affective_belief_persistence.orchestration.contracts import (  # noqa: E402
    ArtifactContract as WorkflowArtifactContract,
)
from affective_belief_persistence.orchestration.contracts import (  # noqa: E402
    HandoffContract as WorkflowHandoffContract,
)
from affective_belief_persistence.orchestration.contracts import (  # noqa: E402
    TaskContract as WorkflowTaskContract,
)
from affective_belief_persistence.orchestration.contracts import WorkerResult  # noqa: E402
from affective_belief_persistence.orchestration.events import WorkflowEvent  # noqa: E402
from affective_belief_persistence.orchestration.state import WorkflowState  # noqa: E402
from affective_belief_persistence.orchestration.workflow import (  # noqa: E402
    WorkflowDefinition,
)

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "agent-config.schema.json": AgentConfig,
    "artifact.schema.json": WorkflowArtifactContract,
    "decision-record.schema.json": DecisionRecord,
    "evaluation-config.schema.json": EvaluationConfig,
    "experiment-config.schema.json": ExperimentSpec,
    "handoff.schema.json": WorkflowHandoffContract,
    "model-config.schema.json": ModelConfig,
    "model-decision.schema.json": ModelDecision,
    "model-request.schema.json": DecisionRequest,
    "resolved-run-config.schema.json": ResolvedRunConfig,
    "run-manifest.schema.json": RunManifest,
    "scenario-config.schema.json": ScenarioConfig,
    "task.schema.json": WorkflowTaskContract,
    "worker-result.schema.json": WorkerResult,
    "workflow-config.schema.json": WorkflowConfig,
    "workflow-definition.schema.json": WorkflowDefinition,
    "workflow-event.schema.json": WorkflowEvent,
    "workflow-state.schema.json": WorkflowState,
}
