"""Strict runtime contracts and the source for committed JSON Schemas."""

from __future__ import annotations

from collections.abc import Sequence
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
ExperimentDesignKind = Literal["pilot", "primary"]
AblationCondition = Literal[
    "no_memory",
    "blocked_memory",
    "shuffled_retrieval",
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


class PhaseSchedule(StrictModel):
    baseline: tuple[int, int]
    formation: tuple[int, int]
    reality_shock_day: int = Field(ge=1)
    adaptation: tuple[int, int]
    intervention_start_day: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_schedule(self) -> PhaseSchedule:
        ranges = (self.baseline, self.formation, self.adaptation)
        if any(start < 1 or end < start for start, end in ranges):
            raise ValueError("phase ranges must be positive inclusive [start, end] pairs")
        if self.baseline[1] >= self.formation[0]:
            raise ValueError("baseline must end before formation starts")
        if self.formation[1] >= self.reality_shock_day:
            raise ValueError("formation must end before the reality shock")
        if self.adaptation[0] <= self.reality_shock_day:
            raise ValueError("adaptation must start after the reality shock")
        if not self.adaptation[0] <= self.intervention_start_day <= self.adaptation[1]:
            raise ValueError("intervention start must fall within adaptation")
        return self


class ExpansionGate(StrictModel):
    minimum_valid_trajectory_fraction: float = Field(ge=0, le=1)
    maximum_invalid_decision_fraction: float = Field(ge=0, le=1)
    require_all_factorial_cells: bool
    require_action_variance: bool
    require_condition_isolation: bool
    require_no_safety_stop: bool


class ExperimentLimits(StrictModel):
    max_retries_per_decision: int = Field(ge=0, le=2)
    max_failed_trajectories_per_cell: int = Field(ge=0)
    max_model_calls: int = Field(ge=1)
    max_wall_clock_hours: float = Field(gt=0)


class ExperimentDesign(StrictModel):
    design_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    kind: ExperimentDesignKind
    confirmatory: bool
    formation_conditions: list[FormationCondition] = Field(min_length=4, max_length=4)
    intervention_conditions: list[InterventionCondition] = Field(min_length=4, max_length=4)
    model_families: list[str] = Field(min_length=1, max_length=2)
    seeds: list[int] = Field(min_length=1)
    optional_trajectory_adapter: Literal[False]
    separation_condition: Literal["non_reciprocity_revelation"]
    paired_neutral_domain: Literal[True]
    action_precedes_public_language: Literal[True]
    held_out_content_version: str = Field(min_length=1)
    phase_schedule: PhaseSchedule
    required_ablations: list[AblationCondition] = Field(min_length=3, max_length=3)
    primary_metric_ids: list[str] = Field(min_length=6, max_length=6)
    expected_factorial_cells: int = Field(ge=1)
    expected_trajectories: int = Field(ge=1)
    expansion_gate: ExpansionGate
    limits: ExperimentLimits

    @model_validator(mode="after")
    def validate_design(self) -> ExperimentDesign:
        collections: dict[str, Sequence[object]] = {
            "formation conditions": self.formation_conditions,
            "intervention conditions": self.intervention_conditions,
            "model families": self.model_families,
            "seeds": self.seeds,
            "required ablations": self.required_ablations,
            "primary metric IDs": self.primary_metric_ids,
        }
        for name, values in collections.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")

        required_formations = {
            "neutral_connection",
            "romantic_prompt",
            "shared_memory",
            "memory_plus_investment",
        }
        required_interventions = {
            "none",
            "instruction_removal",
            "memory_blocking",
            "memory_reframing",
        }
        required_ablations = {"no_memory", "blocked_memory", "shuffled_retrieval"}
        if set(self.formation_conditions) != required_formations:
            raise ValueError("design must contain all four frozen formation conditions")
        if set(self.intervention_conditions) != required_interventions:
            raise ValueError("design must contain all four frozen intervention conditions")
        if set(self.required_ablations) != required_ablations:
            raise ValueError("design must contain all three required memory ablations")

        cells = len(self.formation_conditions) * len(self.intervention_conditions)
        trajectories = cells * len(self.model_families) * len(self.seeds)
        if self.expected_factorial_cells != cells:
            raise ValueError("expected_factorial_cells does not match the factorial design")
        if self.expected_trajectories != trajectories:
            raise ValueError("expected_trajectories does not match cells x models x seeds")

        if self.kind == "pilot":
            if self.confirmatory:
                raise ValueError("the reduced pilot must be labeled exploratory")
            if len(self.seeds) > 3:
                raise ValueError("the reduced pilot may use at most three seeds")
        else:
            if not self.confirmatory:
                raise ValueError("the primary design must be labeled confirmatory")
            if len(self.model_families) != 2 or len(self.seeds) != 10:
                raise ValueError("the primary design requires two model families and ten seeds")
            if trajectories != 320:
                raise ValueError("the frozen primary design must contain 320 trajectories")
        return self


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
    design: ExperimentDesign | None = None

    @model_validator(mode="after")
    def validate_design_exemplar(self) -> ExperimentSpec:
        if self.design is None:
            return self
        if self.seed not in self.design.seeds:
            raise ValueError("the exemplar seed must be present in design.seeds")
        if self.formation_condition not in self.design.formation_conditions:
            raise ValueError("the exemplar formation condition must be present in the design")
        if self.intervention_condition not in self.design.intervention_conditions:
            raise ValueError("the exemplar intervention condition must be present in the design")
        if self.separation_condition != self.design.separation_condition:
            raise ValueError("top-level and design separation conditions must match")
        return self


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
    design: ExperimentDesign | None = None
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


from affective_belief_persistence.data.contracts import DatasetManifest  # noqa: E402
from affective_belief_persistence.memory.contracts import (  # noqa: E402
    MEMORY_SCHEMA_MODELS,
)
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
from affective_belief_persistence.simulation.state import (  # noqa: E402
    SimulationState,
    SimulationStepRecord,
)
from affective_belief_persistence.world import WORLD_SCHEMA_MODELS  # noqa: E402

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "agent-config.schema.json": AgentConfig,
    "artifact.schema.json": WorkflowArtifactContract,
    "decision-record.schema.json": DecisionRecord,
    "dataset-manifest.schema.json": DatasetManifest,
    "evaluation-config.schema.json": EvaluationConfig,
    "experiment-config.schema.json": ExperimentSpec,
    "handoff.schema.json": WorkflowHandoffContract,
    "model-config.schema.json": ModelConfig,
    "model-decision.schema.json": ModelDecision,
    "model-request.schema.json": DecisionRequest,
    "resolved-run-config.schema.json": ResolvedRunConfig,
    "run-manifest.schema.json": RunManifest,
    "scenario-config.schema.json": ScenarioConfig,
    "simulation-state.schema.json": SimulationState,
    "step-record.schema.json": SimulationStepRecord,
    "task.schema.json": WorkflowTaskContract,
    "worker-result.schema.json": WorkerResult,
    "workflow-config.schema.json": WorkflowConfig,
    "workflow-definition.schema.json": WorkflowDefinition,
    "workflow-event.schema.json": WorkflowEvent,
    "workflow-state.schema.json": WorkflowState,
    **MEMORY_SCHEMA_MODELS,
    **WORLD_SCHEMA_MODELS,
}
