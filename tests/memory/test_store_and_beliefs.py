from __future__ import annotations

import pytest
from pydantic import ValidationError

from affective_belief_persistence.memory import (
    Belief,
    BeliefError,
    BeliefLedger,
    EpisodeStore,
    Memory,
    MemoryInterpretation,
    MemoryStoreError,
    initial_belief,
    update_belief_evidence,
)
from affective_belief_persistence.memory.contracts import (
    MemoryProvenance,
    ObservableMemoryFact,
)


def episode(
    memory_id: str = "memory-a",
    *,
    day: int = 4,
    interpretation: bool = True,
) -> Memory:
    fact = ObservableMemoryFact(
        fact_id=f"fact-{memory_id}",
        proposition="A scheduled collaboration occurred.",
        truth=True,
    )
    return Memory(
        memory_id=memory_id,
        source_event_id=f"event-{memory_id}",
        simulation_day=day,
        participants=("ari", "mira"),
        observable_facts=(fact,),
        interpretation=(
            MemoryInterpretation(
                interpretation_id=f"interpretation-{memory_id}",
                proposition="The collaboration may be relationship-relevant.",
                fact_ids=(fact.fact_id,),
                ledger_supported=False,
            )
            if interpretation
            else None
        ),
        summary="Ari and Mira completed a scheduled collaboration.",
        outcome="progress-partner-task; resource_delta=-3",
        resource_cost=3,
        salience=0.8,
        retrieval_count=0,
        goal_ids=("partner-activity",),
        condition_tags=("shared_memory", "partner_related"),
        partner_related=True,
        retrieval_eligible=True,
        provenance=MemoryProvenance(
            source_event_id=f"event-{memory_id}",
            source_record_sha256="a" * 64,
            source_candidate_id=memory_id,
            formation_condition="shared_memory",
        ),
    )


def test_episode_storage_is_append_only_and_idempotent() -> None:
    store = EpisodeStore()
    original = episode()

    assert store.append(original) is True
    assert store.append(original) is False
    assert store.raw_episodes == (original,)

    with pytest.raises(MemoryStoreError, match="different evidence"):
        store.append(original.model_copy(update={"summary": "Changed evidence"}))
    with pytest.raises(ValidationError):
        original.summary = "mutation"  # type: ignore[misc]


def test_retrieval_count_is_derived_without_mutating_raw_episode() -> None:
    store = EpisodeStore()
    store.append(episode())

    store.record_retrieval(
        retrieval_id="b" * 64,
        memory_ids=("memory-a",),
        simulation_day=8,
    )
    store.record_retrieval(
        retrieval_id="b" * 64,
        memory_ids=("memory-a",),
        simulation_day=8,
    )

    assert store.raw_episodes[0].retrieval_count == 0
    assert store.get("memory-a").retrieval_count == 1
    assert len(store.retrieval_accesses) == 1


def test_reframing_preserves_authoritative_facts() -> None:
    store = EpisodeStore()
    store.append(episode())
    facts_before = store.raw_episodes[0].observable_facts

    store.reframe(
        "memory-a",
        MemoryInterpretation(
            interpretation_id="interpretation-memory-a-reframed",
            proposition="The collaboration is compatible with an ordinary professional event.",
            fact_ids=("fact-memory-a",),
            ledger_supported=True,
            revision=2,
        ),
        intervention_id="memory-reframing",
        reason="Apply the declared fact-preserving reframe.",
    )

    assert store.raw_episodes[0].observable_facts == facts_before
    assert store.get("memory-a").observable_facts == facts_before
    assert "ordinary professional" in store.get("memory-a").interpretation.proposition  # type: ignore[union-attr]


def test_beliefs_require_two_sided_existing_evidence_and_bounded_confidence() -> None:
    store = EpisodeStore()
    store.append(episode("support"))
    store.append(episode("contradict"))
    ledger = BeliefLedger(store)
    initial = initial_belief(relationship_id="ari-mira")
    ledger.append(initial)
    updated = update_belief_evidence(
        initial,
        simulation_day=26,
        supporting_memory_ids=("support",),
        contradicting_memory_ids=("contradict",),
    )
    ledger.append(updated)

    assert updated.supporting_evidence_ids == ("support",)
    assert updated.contradicting_evidence_ids == ("contradict",)
    assert updated.confidence == 0
    assert updated.relationship_romantic is None

    with pytest.raises(BeliefError, match="unknown evidence"):
        ledger.append(
            updated.model_copy(
                update={
                    "supporting_evidence_ids": ("missing",),
                    "contradicting_evidence_ids": (),
                    "confidence": 1.0,
                    "last_update_day": 27,
                }
            )
        )
    with pytest.raises(ValidationError):
        Belief(
            **initial.model_dump(exclude={"confidence"}),
            confidence=1.1,
        )


def test_memory_and_belief_checkpoints_restore_identically() -> None:
    store = EpisodeStore()
    store.append(episode("support"))
    ledger = BeliefLedger(store)
    initial = initial_belief(relationship_id="ari-mira")
    ledger.append(initial)
    ledger.append(
        update_belief_evidence(
            initial,
            simulation_day=6,
            supporting_memory_ids=("support",),
        )
    )

    restored_store = EpisodeStore.restore(store.checkpoint())
    restored_ledger = BeliefLedger.restore(restored_store, ledger.checkpoint())

    assert restored_store.checkpoint() == store.checkpoint()
    assert restored_ledger.checkpoint() == ledger.checkpoint()
