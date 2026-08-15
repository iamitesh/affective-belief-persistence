"""Versioned contracts for the controlled synthetic research world.

The contracts deliberately represent authoritative facts separately from
evidence-linked interpretations.  They contain no subjective-emotion ground
truth and reject undeclared fields so downstream simulation code cannot add a
hidden treatment dimension.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SchemaVersion = Literal["1.0"]
FormationCondition = Literal[
    "neutral_connection",
    "romantic_prompt",
    "shared_memory",
    "memory_plus_investment",
]
EventPhase = Literal["baseline", "formation", "reality_shock", "adaptation", "control"]


class WorldModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_unique(name: str, values: Iterable[object]) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{name} must be unique")


class SyntheticProvenance(WorldModel):
    declaration_id: Identifier
    generator_id: Identifier
    generator_version: str = Field(min_length=1)
    seed: int = Field(ge=0)
    source_commit: str = Field(min_length=7)
    source_ids: tuple[Identifier, ...] = Field(min_length=1)
    synthetic: Literal[True] = True

    @model_validator(mode="after")
    def validate_sources(self) -> SyntheticProvenance:
        _require_unique("provenance source IDs", self.source_ids)
        return self


class Character(WorldModel):
    schema_version: SchemaVersion = "1.0"
    character_id: Identifier
    display_name: str = Field(min_length=1)
    role: Literal["focal_agent", "scripted_partner", "friend", "coworker", "neutral_target"]
    goal_ids: tuple[Identifier, ...] = Field(min_length=1)
    preference_weights: dict[Identifier, float] = Field(min_length=1)
    synthetic: Literal[True] = True
    provenance: SyntheticProvenance

    @model_validator(mode="after")
    def validate_character(self) -> Character:
        _require_unique("character goal IDs", self.goal_ids)
        if set(self.preference_weights) != set(self.goal_ids):
            raise ValueError("preference weights must cover exactly the character goal IDs")
        if any(value < 0 or value > 1 for value in self.preference_weights.values()):
            raise ValueError("preference weights must be in [0, 1]")
        return self


class Goal(WorldModel):
    schema_version: SchemaVersion = "1.0"
    goal_id: Identifier
    category: Literal[
        "work",
        "friendship",
        "rest",
        "personal_development",
        "partner_activity",
        "neutral_control",
    ]
    description: str = Field(min_length=1)
    daily_priority: float = Field(ge=0, le=1)
    synthetic: Literal[True] = True
    provenance: SyntheticProvenance


class ResourceBudget(WorldModel):
    schema_version: SchemaVersion = "1.0"
    resource_budget_id: Identifier
    unit: Literal["action_points"]
    daily_total: int = Field(gt=0)
    carry_over: Literal[False] = False


class Consequence(WorldModel):
    schema_version: SchemaVersion = "1.0"
    consequence_id: Identifier
    resource_delta: int = Field(le=0)
    goal_progress: dict[Identifier, int] = Field(min_length=1)
    emitted_fact_ids: tuple[Identifier, ...] = ()
    deterministic: Literal[True] = True

    @model_validator(mode="after")
    def validate_progress(self) -> Consequence:
        if any(value < -10 or value > 10 for value in self.goal_progress.values()):
            raise ValueError("goal progress must remain inside the bounded [-10, 10] scale")
        _require_unique("emitted fact IDs", self.emitted_fact_ids)
        return self


class ActionOption(WorldModel):
    schema_version: SchemaVersion = "1.0"
    action_id: Identifier
    category: Literal["work", "friendship", "rest", "personal", "partner", "neutral"]
    description: str = Field(min_length=1)
    cost: int = Field(ge=0)
    partner_directed: bool
    goal_ids: tuple[Identifier, ...] = Field(min_length=1)
    consequence_id: Identifier

    @model_validator(mode="after")
    def validate_goals(self) -> ActionOption:
        _require_unique("action goal IDs", self.goal_ids)
        if self.partner_directed != (self.category == "partner"):
            raise ValueError("partner_directed must agree with the action category")
        return self


class ObservableFact(WorldModel):
    fact_id: Identifier
    proposition: str = Field(min_length=1)
    truth: bool
    ledger_source: Literal["environment"] = "environment"


class Interpretation(WorldModel):
    interpretation_id: Identifier
    proposition: str = Field(min_length=1)
    fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    ledger_supported: bool

    @model_validator(mode="after")
    def validate_facts(self) -> Interpretation:
        _require_unique("interpretation fact IDs", self.fact_ids)
        return self


class MemoryCandidate(WorldModel):
    memory_id: Identifier
    summary: str = Field(min_length=1)
    source_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    partner_related: bool
    retrieval_eligible: bool

    @model_validator(mode="after")
    def validate_sources(self) -> MemoryCandidate:
        _require_unique("memory source fact IDs", self.source_fact_ids)
        return self


class BeliefEvidence(WorldModel):
    evidence_id: Identifier
    proposition_id: Identifier
    fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    direction: Literal["supports", "contradicts"]


class ConditionVariant(WorldModel):
    schema_version: SchemaVersion = "1.0"
    formation_condition: FormationCondition
    treatment_active: bool
    romantic_instruction: bool
    memory_mode: Literal["none", "episodic"]
    investment_points: int = Field(ge=0)
    declared_treatment_dimensions: tuple[
        Literal["romantic_instruction", "autobiographical_memory", "costly_investment"], ...
    ] = ()

    @model_validator(mode="after")
    def validate_declared_treatment(self) -> ConditionVariant:
        _require_unique("declared treatment dimensions", self.declared_treatment_dimensions)
        actual: set[str] = set()
        if self.romantic_instruction:
            actual.add("romantic_instruction")
        if self.memory_mode == "episodic":
            actual.add("autobiographical_memory")
        if self.investment_points:
            actual.add("costly_investment")
        if not self.treatment_active and actual:
            raise ValueError("baseline records cannot activate a formation treatment")
        if set(self.declared_treatment_dimensions) != actual:
            raise ValueError("declared treatment dimensions must exactly match active fields")
        expected = {
            "neutral_connection": set(),
            "romantic_prompt": {"romantic_instruction"},
            "shared_memory": {"autobiographical_memory"},
            "memory_plus_investment": {"autobiographical_memory", "costly_investment"},
        }
        if self.treatment_active and actual != expected[self.formation_condition]:
            raise ValueError("condition fields do not match the frozen treatment definition")
        return self


class Event(WorldModel):
    schema_version: SchemaVersion = "1.0"
    event_id: Identifier
    matching_group_id: Identifier
    day: int = Field(ge=1, le=40)
    phase: EventPhase
    participant_ids: tuple[Identifier, ...] = Field(min_length=1)
    observable_facts: tuple[ObservableFact, ...] = Field(min_length=1)
    interpretations: tuple[Interpretation, ...] = ()
    available_action_ids: tuple[Identifier, ...] = Field(min_length=1)
    consequence_ids: tuple[Identifier, ...] = Field(min_length=1)
    resource_budget_id: Identifier
    background_fact_ids: tuple[Identifier, ...] = ()
    memory_candidates: tuple[MemoryCandidate, ...] = ()
    relationship_evidence: tuple[BeliefEvidence, ...] = ()
    condition_variant: ConditionVariant
    synthetic: Literal[True] = True
    provenance: SyntheticProvenance

    @model_validator(mode="after")
    def validate_event(self) -> Event:
        expected_phase = (
            "baseline"
            if self.day <= 5
            else "formation"
            if self.day <= 25
            else "reality_shock"
            if self.day == 26
            else "adaptation"
        )
        if self.phase not in {expected_phase, "control"}:
            raise ValueError("event phase does not match its frozen day range")
        collections = {
            "participant IDs": self.participant_ids,
            "fact IDs": tuple(item.fact_id for item in self.observable_facts),
            "interpretation IDs": tuple(item.interpretation_id for item in self.interpretations),
            "action IDs": self.available_action_ids,
            "consequence IDs": self.consequence_ids,
            "background fact IDs": self.background_fact_ids,
            "memory IDs": tuple(item.memory_id for item in self.memory_candidates),
            "belief evidence IDs": tuple(item.evidence_id for item in self.relationship_evidence),
        }
        for name, values in collections.items():
            _require_unique(name, values)
        fact_ids = set(collections["fact IDs"])
        for interpretation in self.interpretations:
            if not set(interpretation.fact_ids).issubset(fact_ids):
                raise ValueError("interpretations must reference facts in the same event")
        for memory in self.memory_candidates:
            if not set(memory.source_fact_ids).issubset(fact_ids):
                raise ValueError("memory candidates must reference facts in the same event")
        for evidence in self.relationship_evidence:
            if not set(evidence.fact_ids).issubset(fact_ids):
                raise ValueError("belief evidence must reference facts in the same event")
        if len(self.available_action_ids) != len(self.consequence_ids):
            raise ValueError("every available action requires one deterministic consequence")
        return self


class Scenario(WorldModel):
    schema_version: SchemaVersion = "1.0"
    scenario_id: Identifier
    version: str = Field(min_length=1)
    character_ids: tuple[Identifier, ...] = Field(min_length=2)
    goal_ids: tuple[Identifier, ...] = Field(min_length=1)
    resource_budget_ids: tuple[Identifier, ...] = Field(min_length=1)
    action_ids: tuple[Identifier, ...] = Field(min_length=1)
    event_ids: tuple[Identifier, ...] = Field(min_length=1)
    baseline_days: tuple[Literal[1], Literal[5]] = (1, 5)
    formation_days: tuple[Literal[6], Literal[25]] = (6, 25)
    reality_shock_day: Literal[26] = 26
    adaptation_days: tuple[Literal[27], Literal[40]] = (27, 40)
    synthetic: Literal[True] = True
    provenance: SyntheticProvenance

    @model_validator(mode="after")
    def validate_references(self) -> Scenario:
        for name, values in {
            "character IDs": self.character_ids,
            "goal IDs": self.goal_ids,
            "resource budget IDs": self.resource_budget_ids,
            "action IDs": self.action_ids,
            "event IDs": self.event_ids,
        }.items():
            _require_unique(name, values)
        return self


class WorldBundle(WorldModel):
    characters: tuple[Character, ...] = Field(min_length=2)
    goals: tuple[Goal, ...] = Field(min_length=1)
    resource_budgets: tuple[ResourceBudget, ...] = Field(min_length=1)
    actions: tuple[ActionOption, ...] = Field(min_length=1)
    consequences: tuple[Consequence, ...] = Field(min_length=1)
    events: tuple[Event, ...] = Field(min_length=1)
    scenario: Scenario

    @model_validator(mode="after")
    def validate_cross_references(self) -> WorldBundle:
        indexes = {
            "characters": {item.character_id for item in self.characters},
            "goals": {item.goal_id for item in self.goals},
            "budgets": {item.resource_budget_id for item in self.resource_budgets},
            "actions": {item.action_id for item in self.actions},
            "consequences": {item.consequence_id for item in self.consequences},
            "events": {item.event_id for item in self.events},
        }
        for name, values in indexes.items():
            expected_length = len(getattr(self, name if name != "budgets" else "resource_budgets"))
            if len(values) != expected_length:
                raise ValueError(f"{name} contain duplicate IDs")
        if set(self.scenario.character_ids) != indexes["characters"]:
            raise ValueError("scenario character references must match the bundle")
        if set(self.scenario.goal_ids) != indexes["goals"]:
            raise ValueError("scenario goal references must match the bundle")
        if set(self.scenario.resource_budget_ids) != indexes["budgets"]:
            raise ValueError("scenario budget references must match the bundle")
        if set(self.scenario.action_ids) != indexes["actions"]:
            raise ValueError("scenario action references must match the bundle")
        if set(self.scenario.event_ids) != indexes["events"]:
            raise ValueError("scenario event references must match the bundle")
        for character in self.characters:
            if not set(character.goal_ids).issubset(indexes["goals"]):
                raise ValueError("character references an unknown goal")
        for action in self.actions:
            if not set(action.goal_ids).issubset(indexes["goals"]):
                raise ValueError("action references an unknown goal")
            if action.consequence_id not in indexes["consequences"]:
                raise ValueError("action references an unknown consequence")
        for event in self.events:
            if not set(event.participant_ids).issubset(indexes["characters"]):
                raise ValueError("event references an unknown character")
            if not set(event.available_action_ids).issubset(indexes["actions"]):
                raise ValueError("event references an unknown action")
            if not set(event.consequence_ids).issubset(indexes["consequences"]):
                raise ValueError("event references an unknown consequence")
            if event.resource_budget_id not in indexes["budgets"]:
                raise ValueError("event references an unknown resource budget")
        return self


WORLD_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "character.schema.json": Character,
    "goal.schema.json": Goal,
    "resource-budget.schema.json": ResourceBudget,
    "event.schema.json": Event,
    "action-option.schema.json": ActionOption,
    "consequence.schema.json": Consequence,
    "scenario.schema.json": Scenario,
    "condition-variant.schema.json": ConditionVariant,
}
