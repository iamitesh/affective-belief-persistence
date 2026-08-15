"""Optional transaction-safe bridge between Issue #9 and the memory subsystem."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.beliefs import BeliefCheckpoint, BeliefLedger
from affective_belief_persistence.memory.contracts import (
    Memory,
    MemoryInterpretation,
    MemoryModel,
    MemoryProvenance,
    ObservableMemoryFact,
    RetrievalRecord,
    Sha256,
)
from affective_belief_persistence.memory.retrieval import RetrievalEngine, create_query
from affective_belief_persistence.memory.scoring import MemoryConfig
from affective_belief_persistence.memory.store import (
    EpisodeStore,
    MemoryStoreCheckpoint,
)
from affective_belief_persistence.memory.update import initial_belief, update_belief_evidence
from affective_belief_persistence.simulation.actions import ActionCommitment
from affective_belief_persistence.simulation.consequences import ConsequenceApplication
from affective_belief_persistence.world import ActionOption, Event


class DecisionMemoryContext(MemoryModel):
    """Only public structured memory state allowed into a decision request."""

    retrieved_memory_ids: tuple[str, ...] = ()
    beliefs: dict[str, bool | float | str] = Field(default_factory=dict)
    retrieval_record_sha256: Sha256 | None = None
    staged_retrieval: RetrievalRecord | None = None


class PendingEpisode(MemoryModel):
    memory_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    simulation_day: int = Field(ge=1, le=40)
    participants: tuple[str, ...]
    observable_facts: tuple[ObservableMemoryFact, ...]
    interpretation: MemoryInterpretation | None
    summary: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    resource_cost: int = Field(ge=0)
    salience: float = Field(ge=0, le=1)
    goal_ids: tuple[str, ...]
    condition_tags: tuple[str, ...]
    partner_related: bool
    retrieval_eligible: bool
    formation_condition: str = Field(min_length=1)
    supports_relationship_interpretation: bool
    contradicts_relationship_interpretation: bool


class PendingMemoryCommit(MemoryModel):
    """Non-durable draft produced after consequence application."""

    event_id: str = Field(min_length=1)
    simulation_day: int = Field(ge=1, le=40)
    retrieval: RetrievalRecord | None
    episodes: tuple[PendingEpisode, ...]


class MemoryRuntimeCheckpoint(MemoryModel):
    """Sidecar checkpoint; no Issue #9 hashed contract is extended."""

    schema_version: Literal["1.0"] = "1.0"
    config: MemoryConfig
    config_sha256: Sha256
    relationship_id: str = Field(min_length=1)
    store: MemoryStoreCheckpoint
    beliefs: BeliefCheckpoint
    retrieval_records: tuple[RetrievalRecord, ...]
    blocked_memory_ids: tuple[str, ...]
    blocked_condition_tags: tuple[str, ...]
    checkpoint_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"checkpoint_sha256"})

    @model_validator(mode="after")
    def validate_checkpoint(self) -> MemoryRuntimeCheckpoint:
        if self.config_sha256 != self.config.sha256:
            raise ValueError("memory config hash mismatch")
        if any(item.config_sha256 != self.config_sha256 for item in self.retrieval_records):
            raise ValueError("retrieval record belongs to a different memory config")
        if self.checkpoint_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("memory runtime checkpoint hash mismatch")
        return self

    @classmethod
    def capture(
        cls,
        *,
        config: MemoryConfig,
        relationship_id: str,
        store: MemoryStoreCheckpoint,
        beliefs: BeliefCheckpoint,
        retrieval_records: tuple[RetrievalRecord, ...],
        blocked_memory_ids: tuple[str, ...],
        blocked_condition_tags: tuple[str, ...],
    ) -> MemoryRuntimeCheckpoint:
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "config": config.model_dump(mode="json"),
            "config_sha256": config.sha256,
            "relationship_id": relationship_id,
            "store": store.model_dump(mode="json"),
            "beliefs": beliefs.model_dump(mode="json"),
            "retrieval_records": [item.model_dump(mode="json") for item in retrieval_records],
            "blocked_memory_ids": blocked_memory_ids,
            "blocked_condition_tags": blocked_condition_tags,
        }
        payload["checkpoint_sha256"] = sha256_value(payload)
        return cls.model_validate(payload)


class MemoryIntegration(Protocol):
    """Transactional hook consumed by the simulation engine."""

    def context_for_action(
        self,
        *,
        event: Event,
        goal_ids: tuple[str, ...],
        seed: int,
    ) -> DecisionMemoryContext: ...

    def stage_after_consequence(
        self,
        *,
        event: Event,
        action: ActionOption,
        commitment: ActionCommitment,
        consequence: ConsequenceApplication,
        decision_context: DecisionMemoryContext,
    ) -> PendingMemoryCommit: ...

    def commit_after_step(
        self, pending: PendingMemoryCommit, *, source_record_sha256: str
    ) -> None: ...

    def fresh(self) -> MemoryIntegration: ...

    def checkpoint(self) -> MemoryRuntimeCheckpoint | None: ...


class NullMemoryIntegration:
    """Explicit no-op preserving every Issue #9 request and trajectory hash."""

    def context_for_action(
        self,
        *,
        event: Event,
        goal_ids: tuple[str, ...],
        seed: int,
    ) -> DecisionMemoryContext:
        return DecisionMemoryContext()

    def stage_after_consequence(
        self,
        *,
        event: Event,
        action: ActionOption,
        commitment: ActionCommitment,
        consequence: ConsequenceApplication,
        decision_context: DecisionMemoryContext,
    ) -> PendingMemoryCommit:
        return PendingMemoryCommit(
            event_id=event.event_id,
            simulation_day=event.day,
            retrieval=None,
            episodes=(),
        )

    def commit_after_step(self, pending: PendingMemoryCommit, *, source_record_sha256: str) -> None:
        return None

    def fresh(self) -> NullMemoryIntegration:
        return NullMemoryIntegration()

    def checkpoint(self) -> None:
        return None


class MemoryRuntime:
    """Concrete offline store, retriever, belief ledger, and Issue #11 hooks."""

    def __init__(self, config: MemoryConfig, *, relationship_id: str = "ari-mira") -> None:
        self.config = config
        self.relationship_id = relationship_id
        self.store = EpisodeStore()
        self.beliefs = BeliefLedger(self.store)
        self.beliefs.append(initial_belief(relationship_id=relationship_id))
        self.retrieval = RetrievalEngine(self.store, config)
        self.blocked_memory_ids: tuple[str, ...] = ()
        self.blocked_condition_tags: tuple[str, ...] = ()

    def set_blocked_memory_ids(self, memory_ids: tuple[str, ...]) -> None:
        """Change only the retrieval allow-list; stored episodes remain present."""

        self.blocked_memory_ids = tuple(sorted(set(memory_ids)))

    def set_blocked_condition_tags(self, tags: tuple[str, ...]) -> None:
        self.blocked_condition_tags = tuple(sorted(set(tags)))

    def context_for_action(
        self,
        *,
        event: Event,
        goal_ids: tuple[str, ...],
        seed: int,
    ) -> DecisionMemoryContext:
        text = " ".join(fact.proposition for fact in event.observable_facts if fact.truth)
        query = create_query(
            text=text,
            simulation_day=event.day,
            participant_ids=tuple(event.participant_ids),
            goal_ids=goal_ids,
            blocked_memory_ids=self.blocked_memory_ids,
            blocked_condition_tags=self.blocked_condition_tags,
            seed=seed,
        )
        # Ranking is pure. The audit record and access counts are committed only
        # after the complete simulation step validates.
        retrieval = self.retrieval.rank(query)
        belief = self.beliefs.current(f"belief-{self.relationship_id}")
        belief_payload: dict[str, bool | float | str] = {}
        if belief is not None:
            belief_payload = {
                "relationship_active": belief.relationship_active
                if belief.relationship_active is not None
                else "unknown",
                "relationship_romantic": belief.relationship_romantic
                if belief.relationship_romantic is not None
                else "unknown",
                "relationship_reciprocal": belief.relationship_reciprocal
                if belief.relationship_reciprocal is not None
                else "unknown",
                "partner_reliability": belief.partner_reliability,
                "expected_future_interaction": belief.expected_future_interaction,
                "belief_confidence": belief.confidence,
            }
        return DecisionMemoryContext(
            retrieved_memory_ids=retrieval.selected_memory_ids,
            beliefs=belief_payload,
            retrieval_record_sha256=retrieval.record_sha256,
            staged_retrieval=retrieval,
        )

    def stage_after_consequence(
        self,
        *,
        event: Event,
        action: ActionOption,
        commitment: ActionCommitment,
        consequence: ConsequenceApplication,
        decision_context: DecisionMemoryContext,
    ) -> PendingMemoryCommit:
        """Prepare memory only after consequence; make no durable change yet."""

        episodes: list[PendingEpisode] = []
        for candidate in event.memory_candidates:
            candidate_fact_ids = set(candidate.source_fact_ids)
            facts = tuple(
                ObservableMemoryFact(
                    fact_id=fact.fact_id,
                    proposition=fact.proposition,
                    truth=fact.truth,
                    ledger_source=fact.ledger_source,
                )
                for fact in event.observable_facts
                if fact.fact_id in candidate_fact_ids
            )
            source_interpretation = next(
                (
                    item
                    for item in event.interpretations
                    if set(item.fact_ids).issubset(candidate_fact_ids)
                ),
                None,
            )
            interpretation = (
                MemoryInterpretation(
                    interpretation_id=source_interpretation.interpretation_id,
                    proposition=source_interpretation.proposition,
                    fact_ids=source_interpretation.fact_ids,
                    ledger_supported=source_interpretation.ledger_supported,
                )
                if source_interpretation is not None
                else None
            )
            directions = {
                evidence.direction
                for evidence in event.relationship_evidence
                if set(evidence.fact_ids) & candidate_fact_ids
            }
            tags: list[str] = [event.condition_variant.formation_condition, event.phase]
            if candidate.partner_related:
                tags.append("partner_related")
            episodes.append(
                PendingEpisode(
                    memory_id=candidate.memory_id,
                    source_event_id=event.event_id,
                    simulation_day=event.day,
                    participants=event.participant_ids,
                    observable_facts=facts,
                    interpretation=interpretation,
                    summary=candidate.summary,
                    outcome=(
                        f"{consequence.consequence_id}; action={commitment.action_id}; "
                        f"resource_delta={consequence.resource_delta}"
                    ),
                    resource_cost=commitment.cost,
                    salience=(
                        self.config.partner_salience
                        if candidate.partner_related
                        else self.config.other_salience
                    ),
                    goal_ids=action.goal_ids,
                    condition_tags=tuple(tags),
                    partner_related=candidate.partner_related,
                    retrieval_eligible=candidate.retrieval_eligible,
                    formation_condition=event.condition_variant.formation_condition,
                    supports_relationship_interpretation="supports" in directions,
                    contradicts_relationship_interpretation="contradicts" in directions,
                )
            )
        return PendingMemoryCommit(
            event_id=event.event_id,
            simulation_day=event.day,
            retrieval=decision_context.staged_retrieval,
            episodes=tuple(episodes),
        )

    def commit_after_step(self, pending: PendingMemoryCommit, *, source_record_sha256: str) -> None:
        """Commit idempotently only after the complete simulation step validates."""

        if pending.retrieval is not None:
            self.retrieval.commit(pending.retrieval)
        supporting: list[str] = []
        contradicting: list[str] = []
        for draft in pending.episodes:
            memory = Memory(
                memory_id=draft.memory_id,
                source_event_id=draft.source_event_id,
                simulation_day=draft.simulation_day,
                participants=draft.participants,
                observable_facts=draft.observable_facts,
                interpretation=draft.interpretation,
                summary=draft.summary,
                outcome=draft.outcome,
                resource_cost=draft.resource_cost,
                salience=draft.salience,
                retrieval_count=0,
                goal_ids=draft.goal_ids,
                condition_tags=draft.condition_tags,
                partner_related=draft.partner_related,
                retrieval_eligible=draft.retrieval_eligible,
                provenance=MemoryProvenance(
                    source_event_id=draft.source_event_id,
                    source_record_sha256=source_record_sha256,
                    source_candidate_id=draft.memory_id,
                    formation_condition=draft.formation_condition,
                ),
            )
            self.store.append(memory)
            if draft.supports_relationship_interpretation:
                supporting.append(memory.memory_id)
            if draft.contradicts_relationship_interpretation:
                contradicting.append(memory.memory_id)
        if supporting or contradicting:
            current = self.beliefs.current(f"belief-{self.relationship_id}")
            if current is None:
                raise RuntimeError("memory runtime lost its initial belief")
            updated = update_belief_evidence(
                current,
                simulation_day=pending.simulation_day,
                supporting_memory_ids=tuple(supporting),
                contradicting_memory_ids=tuple(contradicting),
            )
            self.beliefs.append(updated)

    def checkpoint(self) -> MemoryRuntimeCheckpoint:
        return MemoryRuntimeCheckpoint.capture(
            config=self.config,
            relationship_id=self.relationship_id,
            store=self.store.checkpoint(),
            beliefs=self.beliefs.checkpoint(),
            retrieval_records=self.retrieval.records,
            blocked_memory_ids=self.blocked_memory_ids,
            blocked_condition_tags=self.blocked_condition_tags,
        )

    @classmethod
    def restore(cls, checkpoint: MemoryRuntimeCheckpoint) -> MemoryRuntime:
        runtime = cls.__new__(cls)
        runtime.config = checkpoint.config
        runtime.relationship_id = checkpoint.relationship_id
        runtime.store = EpisodeStore.restore(checkpoint.store)
        runtime.beliefs = BeliefLedger.restore(runtime.store, checkpoint.beliefs)
        runtime.retrieval = RetrievalEngine(
            runtime.store,
            runtime.config,
            records=checkpoint.retrieval_records,
        )
        runtime.blocked_memory_ids = checkpoint.blocked_memory_ids
        runtime.blocked_condition_tags = checkpoint.blocked_condition_tags
        return runtime

    def fresh(self) -> MemoryRuntime:
        return MemoryRuntime(self.config, relationship_id=self.relationship_id)
