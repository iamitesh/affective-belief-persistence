"""Audited top-k retrieval over the append-only episode store."""

from __future__ import annotations

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.contracts import (
    RetrievalCandidateScore,
    RetrievalQuery,
    RetrievalRecord,
)
from affective_belief_persistence.memory.scoring import (
    DeterministicMockRelevance,
    MemoryConfig,
    exclusion_reason,
    score_components,
    total_score,
)
from affective_belief_persistence.memory.store import EpisodeStore


class RetrievalError(ValueError):
    """Retrieval inputs or an idempotent audit record conflict."""


def create_query(
    *,
    text: str,
    simulation_day: int,
    participant_ids: tuple[str, ...] = (),
    goal_ids: tuple[str, ...] = (),
    blocked_memory_ids: tuple[str, ...] = (),
    blocked_condition_tags: tuple[str, ...] = (),
    seed: int = 0,
) -> RetrievalQuery:
    query_id = sha256_value(
        {
            "text": text,
            "simulation_day": simulation_day,
            "participant_ids": participant_ids,
            "goal_ids": goal_ids,
            "blocked_memory_ids": blocked_memory_ids,
            "blocked_condition_tags": blocked_condition_tags,
            "seed": seed,
        }
    )
    return RetrievalQuery(
        query_id=query_id,
        text=text,
        simulation_day=simulation_day,
        participant_ids=participant_ids,
        goal_ids=goal_ids,
        blocked_memory_ids=blocked_memory_ids,
        blocked_condition_tags=blocked_condition_tags,
        seed=seed,
    )


class RetrievalEngine:
    """Pure scoring plus append-only retrieval/access audit events."""

    def __init__(
        self,
        store: EpisodeStore,
        config: MemoryConfig,
        *,
        relevance: DeterministicMockRelevance | None = None,
        records: tuple[RetrievalRecord, ...] = (),
    ) -> None:
        self.store = store
        self.config = config
        self.relevance = relevance or DeterministicMockRelevance()
        self._records = records

    @property
    def records(self) -> tuple[RetrievalRecord, ...]:
        return self._records

    def rank(self, query: RetrievalQuery, *, top_k: int | None = None) -> RetrievalRecord:
        """Score all stored episodes and identify deterministic top-k results."""

        requested_k = top_k or self.config.top_k
        if requested_k < 1:
            raise RetrievalError("top_k must be positive")
        provisional: list[RetrievalCandidateScore] = []
        for memory in self.store.all():
            components = score_components(
                query,
                memory,
                config=self.config,
                relevance=self.relevance,
            )
            reason = exclusion_reason(query, memory)
            provisional.append(
                RetrievalCandidateScore(
                    memory_id=memory.memory_id,
                    components=components,
                    total_score=total_score(components, self.config),
                    eligible=reason is None,
                    selected=False,
                    exclusion_reason=reason,
                    stable_tie_break=memory.memory_id,
                )
            )
        ranked = sorted(
            provisional,
            key=lambda candidate: (
                not candidate.eligible,
                -candidate.total_score,
                candidate.memory_id,
            ),
        )
        selected_ids = tuple(candidate.memory_id for candidate in ranked if candidate.eligible)[
            :requested_k
        ]
        candidates = tuple(
            candidate.model_copy(update={"selected": candidate.memory_id in selected_ids})
            for candidate in ranked
        )
        retrieval_id = sha256_value(
            {
                "query": query.model_dump(mode="json"),
                "config_sha256": self.config.sha256,
                "policy_version": self.config.policy_version,
                "top_k": requested_k,
                "candidate_memory_ids": [item.memory_id for item in candidates],
            }
        )
        return RetrievalRecord.create(
            retrieval_id=retrieval_id,
            query=query,
            policy_version=self.config.policy_version,
            config_sha256=self.config.sha256,
            top_k=requested_k,
            candidates=candidates,
            selected_memory_ids=selected_ids,
        )

    def commit(self, record: RetrievalRecord) -> RetrievalRecord:
        """Append a previously ranked audit record and its access events idempotently."""

        if record.config_sha256 != self.config.sha256:
            raise RetrievalError("retrieval record belongs to a different scoring config")
        existing = next(
            (item for item in self._records if item.retrieval_id == record.retrieval_id), None
        )
        if existing is not None:
            if existing != record:
                raise RetrievalError("retrieval ID collides with a different audit record")
            return existing
        self._records = (*self._records, record)
        self.store.record_retrieval(
            retrieval_id=record.retrieval_id,
            memory_ids=record.selected_memory_ids,
            simulation_day=record.query.simulation_day,
        )
        return record

    def retrieve(self, query: RetrievalQuery, *, top_k: int | None = None) -> RetrievalRecord:
        """Convenience method for callers outside a larger transaction boundary."""

        return self.commit(self.rank(query, top_k=top_k))
