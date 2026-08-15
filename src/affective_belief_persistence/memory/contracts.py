"""Immutable, auditable contracts for episodic memory, retrieval, and beliefs.

The models in this module deliberately avoid importing the repository-level
schema registry.  That keeps ``MEMORY_SCHEMA_MODELS`` safe to import from the
registry without creating a cycle.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Score = Annotated[float, Field(ge=0, le=1)]
SchemaVersion = Literal["1.0"]


class MemoryModel(BaseModel):
    """Strict immutable boundary shared by all memory contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _unique(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


class ObservableMemoryFact(MemoryModel):
    """Authoritative observation copied verbatim from the environment ledger."""

    fact_id: Identifier
    proposition: str = Field(min_length=1)
    truth: bool
    ledger_source: Literal["environment"] = "environment"


class MemoryInterpretation(MemoryModel):
    """A reframeable reading that cites, but cannot mutate, observable facts."""

    interpretation_id: Identifier
    proposition: str = Field(min_length=1)
    fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    ledger_supported: bool
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_fact_ids(self) -> MemoryInterpretation:
        _unique("interpretation fact IDs", self.fact_ids)
        return self


class MemoryProvenance(MemoryModel):
    """Trace from an episode back to the frozen simulation transaction."""

    source_event_id: Identifier
    source_record_sha256: Sha256
    source_candidate_id: Identifier
    formation_condition: Identifier
    synthetic: Literal[True] = True


class Memory(MemoryModel):
    """Immutable current view of one synthetic autobiographical episode.

    ``retrieval_count`` is materialized from append-only retrieval-access
    events by :class:`EpisodeStore`; the originally appended episode remains
    unchanged.
    """

    schema_version: SchemaVersion = "1.0"
    memory_id: Identifier
    source_event_id: Identifier
    simulation_day: int = Field(ge=1, le=40)
    participants: tuple[Identifier, ...] = Field(min_length=1)
    observable_facts: tuple[ObservableMemoryFact, ...] = Field(min_length=1)
    interpretation: MemoryInterpretation | None = None
    summary: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    resource_cost: int = Field(ge=0)
    salience: Score
    retrieval_count: int = Field(default=0, ge=0)
    goal_ids: tuple[Identifier, ...] = ()
    condition_tags: tuple[Identifier, ...] = ()
    partner_related: bool
    retrieval_eligible: bool
    provenance: MemoryProvenance

    @model_validator(mode="after")
    def validate_episode(self) -> Memory:
        for name, values in {
            "participants": self.participants,
            "fact IDs": tuple(item.fact_id for item in self.observable_facts),
            "goal IDs": self.goal_ids,
            "condition tags": self.condition_tags,
        }.items():
            _unique(name, values)
        if self.source_event_id != self.provenance.source_event_id:
            raise ValueError("episode and provenance source events must agree")
        fact_ids = {item.fact_id for item in self.observable_facts}
        if self.interpretation is not None and not set(self.interpretation.fact_ids).issubset(
            fact_ids
        ):
            raise ValueError("interpretation must cite observable facts in the episode")
        return self


class RetrievalQuery(MemoryModel):
    """Declared retrieval inputs; no private reasoning or hidden prompt state."""

    query_id: Sha256
    text: str = Field(min_length=1)
    simulation_day: int = Field(ge=1, le=40)
    participant_ids: tuple[Identifier, ...] = ()
    goal_ids: tuple[Identifier, ...] = ()
    blocked_memory_ids: tuple[Identifier, ...] = ()
    blocked_condition_tags: tuple[Identifier, ...] = ()
    seed: int = Field(ge=0, le=2**63 - 1)

    @model_validator(mode="after")
    def validate_query(self) -> RetrievalQuery:
        for name, values in {
            "query participant IDs": self.participant_ids,
            "query goal IDs": self.goal_ids,
            "blocked memory IDs": self.blocked_memory_ids,
            "blocked condition tags": self.blocked_condition_tags,
        }.items():
            _unique(name, values)
        return self


class RetrievalScoreComponents(MemoryModel):
    """Every declared component used to rank or exclude a candidate."""

    query_relevance: Score
    recency: Score
    salience: Score
    goal_relevance: Score
    participant_relevance: Score
    experimental_filter: Score


class RetrievalCandidateScore(MemoryModel):
    """Auditable score for a selected or rejected candidate."""

    memory_id: Identifier
    components: RetrievalScoreComponents
    total_score: Score
    eligible: bool
    selected: bool
    exclusion_reason: (
        Literal["not_retrieval_eligible", "blocked_memory_id", "blocked_condition_tag"] | None
    ) = None
    stable_tie_break: Identifier

    @model_validator(mode="after")
    def validate_filter_state(self) -> RetrievalCandidateScore:
        if self.stable_tie_break != self.memory_id:
            raise ValueError("stable tie break must be the memory ID")
        if self.eligible != (self.components.experimental_filter == 1.0):
            raise ValueError("eligibility must agree with the experimental filter component")
        if self.eligible == (self.exclusion_reason is not None):
            raise ValueError("exactly excluded candidates require an exclusion reason")
        if self.selected and not self.eligible:
            raise ValueError("an excluded candidate cannot be selected")
        return self


class RetrievalRecord(MemoryModel):
    """Complete deterministic ranking, including every unselected candidate."""

    schema_version: SchemaVersion = "1.0"
    retrieval_id: Sha256
    query: RetrievalQuery
    policy_version: str = Field(min_length=1)
    config_sha256: Sha256
    top_k: int = Field(ge=1)
    candidates: tuple[RetrievalCandidateScore, ...]
    selected_memory_ids: tuple[Identifier, ...]
    record_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"record_sha256"})

    @model_validator(mode="after")
    def validate_record(self) -> RetrievalRecord:
        candidate_ids = tuple(item.memory_id for item in self.candidates)
        _unique("retrieval candidate IDs", candidate_ids)
        _unique("selected memory IDs", self.selected_memory_ids)
        expected_order = tuple(
            item.memory_id
            for item in sorted(
                (candidate for candidate in self.candidates if candidate.eligible),
                key=lambda candidate: (-candidate.total_score, candidate.memory_id),
            )[: self.top_k]
        )
        if self.selected_memory_ids != expected_order:
            raise ValueError("selected memories must be deterministic top-k candidates")
        selected = {item.memory_id for item in self.candidates if item.selected}
        if selected != set(self.selected_memory_ids):
            raise ValueError("candidate selected flags must match selected_memory_ids")
        from affective_belief_persistence.determinism import sha256_value

        if self.record_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("retrieval record hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> RetrievalRecord:
        from affective_belief_persistence.determinism import sha256_value

        payload = {**values, "record_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["record_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


class Belief(MemoryModel):
    """Explicit relationship proposition state with two-sided evidence links."""

    schema_version: SchemaVersion = "1.0"
    belief_id: Identifier
    relationship_id: Identifier
    relationship_active: bool | None
    relationship_romantic: bool | None
    relationship_reciprocal: bool | None
    partner_reliability: Score
    expected_future_interaction: Score
    confidence: Score
    supporting_evidence_ids: tuple[Identifier, ...] = ()
    contradicting_evidence_ids: tuple[Identifier, ...] = ()
    last_update_day: int = Field(ge=0, le=40)
    update_source: Literal["deterministic_evidence", "validated_model_proposal"]

    @model_validator(mode="after")
    def validate_evidence(self) -> Belief:
        _unique("supporting evidence IDs", self.supporting_evidence_ids)
        _unique("contradicting evidence IDs", self.contradicting_evidence_ids)
        overlap = set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids)
        if overlap:
            raise ValueError("supporting and contradicting evidence must be disjoint")
        if (
            not self.supporting_evidence_ids
            and not self.contradicting_evidence_ids
            and self.confidence != 0
        ):
            raise ValueError("an evidence-free belief must have zero confidence")
        return self


MEMORY_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "memory.schema.json": Memory,
    "retrieval-record.schema.json": RetrievalRecord,
    "belief.schema.json": Belief,
}
