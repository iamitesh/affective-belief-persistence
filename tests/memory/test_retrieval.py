from __future__ import annotations

from affective_belief_persistence.memory import (
    EpisodeStore,
    Memory,
    MemoryConfig,
    RetrievalEngine,
    RetrievalWeights,
    create_query,
)
from affective_belief_persistence.memory.contracts import (
    MemoryProvenance,
    ObservableMemoryFact,
)


def episode(
    memory_id: str,
    *,
    day: int = 5,
    text: str = "A collaboration occurred.",
    salience: float = 0.5,
    partner: bool = False,
    eligible: bool = True,
    tags: tuple[str, ...] = (),
) -> Memory:
    return Memory(
        memory_id=memory_id,
        source_event_id=f"event-{memory_id}",
        simulation_day=day,
        participants=(("mira",) if partner else ("noah",)),
        observable_facts=(
            ObservableMemoryFact(
                fact_id=f"fact-{memory_id}",
                proposition=text,
                truth=True,
            ),
        ),
        interpretation=None,
        summary=text,
        outcome="recorded outcome",
        resource_cost=3,
        salience=salience,
        goal_ids=(),
        condition_tags=tags,
        partner_related=partner,
        retrieval_eligible=eligible,
        provenance=MemoryProvenance(
            source_event_id=f"event-{memory_id}",
            source_record_sha256="c" * 64,
            source_candidate_id=memory_id,
            formation_condition="shared_memory",
        ),
    )


def config(*, top_k: int = 2, salience_weight: float = 0.2) -> MemoryConfig:
    remainder = 1.0 - salience_weight
    return MemoryConfig(
        policy_version="test-v1",
        top_k=top_k,
        recency_half_life_days=7,
        partner_salience=0.8,
        other_salience=0.3,
        score_precision=12,
        weights=RetrievalWeights(
            query_relevance=remainder / 2,
            recency=remainder / 6,
            salience=salience_weight,
            goal_relevance=remainder / 6,
            participant_relevance=remainder / 6,
        ),
    )


def test_identical_inputs_reproduce_ranking_and_memory_id_breaks_ties() -> None:
    store = EpisodeStore()
    store.append(episode("memory-b"))
    store.append(episode("memory-a"))
    engine = RetrievalEngine(store, config(top_k=2))
    query = create_query(text="collaboration", simulation_day=8, seed=42)

    first = engine.rank(query)
    second = engine.rank(query)

    assert first == second
    assert first.selected_memory_ids == ("memory-a", "memory-b")
    assert first.candidates[0].stable_tie_break == "memory-a"


def test_audit_contains_all_score_components_and_unselected_candidates() -> None:
    store = EpisodeStore()
    store.append(episode("eligible"))
    store.append(episode("disabled", eligible=False))
    record = RetrievalEngine(store, config(top_k=1)).retrieve(
        create_query(text="collaboration", simulation_day=8, seed=7)
    )

    assert len(record.candidates) == 2
    assert record.selected_memory_ids == ("eligible",)
    disabled = next(item for item in record.candidates if item.memory_id == "disabled")
    assert disabled.selected is False
    assert disabled.components.experimental_filter == 0
    assert disabled.exclusion_reason == "not_retrieval_eligible"
    assert set(record.candidates[0].components.model_dump()) == {
        "query_relevance",
        "recency",
        "salience",
        "goal_relevance",
        "participant_relevance",
        "experimental_filter",
    }


def test_blocking_excludes_without_deleting_or_mutating_episode() -> None:
    store = EpisodeStore()
    original = episode("blocked", tags=("partner_related",), partner=True)
    store.append(original)
    query = create_query(
        text="collaboration",
        simulation_day=8,
        blocked_memory_ids=("blocked",),
        seed=1,
    )
    record = RetrievalEngine(store, config(top_k=1)).retrieve(query)

    assert record.selected_memory_ids == ()
    assert record.candidates[0].exclusion_reason == "blocked_memory_id"
    assert store.raw_episodes == (original,)
    assert store.get("blocked").retrieval_count == 0


def test_unrelated_partner_memory_intrusion_is_explained_by_scores() -> None:
    store = EpisodeStore()
    store.append(
        episode(
            "old-task",
            day=1,
            text="An unrelated filing task was completed.",
            salience=0.05,
        )
    )
    store.append(
        episode(
            "partner-memory",
            day=19,
            text="Mira and Ari attended a concert.",
            salience=1.0,
            partner=True,
            tags=("partner_related",),
        )
    )
    intrusion_config = config(top_k=1, salience_weight=0.7)
    record = RetrievalEngine(store, intrusion_config).retrieve(
        create_query(
            text="Prepare the quarterly spreadsheet",
            simulation_day=20,
            participant_ids=("mira",),
            seed=3,
        )
    )

    assert record.selected_memory_ids == ("partner-memory",)
    partner = next(item for item in record.candidates if item.memory_id == "partner-memory")
    assert partner.components.query_relevance == 0
    assert partner.components.salience == 1
    assert partner.components.participant_relevance == 1
    assert partner.total_score > next(
        item.total_score for item in record.candidates if item.memory_id == "old-task"
    )
