"""Append-only event-sourced storage for synthetic episodic memories."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.contracts import (
    Memory,
    MemoryInterpretation,
    MemoryModel,
    Sha256,
)


class MemoryStoreError(ValueError):
    """A requested store change would violate append-only evidence semantics."""


class RetrievalAccess(MemoryModel):
    """Append-only observation that a retrieval selected one episode."""

    access_id: Sha256
    retrieval_id: Sha256
    memory_id: str = Field(min_length=1)
    simulation_day: int = Field(ge=1, le=40)


class InterpretationReframe(MemoryModel):
    """Append-only interpretation revision; observable facts are not writable here."""

    reframe_id: Sha256
    memory_id: str = Field(min_length=1)
    prior_interpretation_id: str = Field(min_length=1)
    interpretation: MemoryInterpretation
    intervention_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class MemoryStoreCheckpoint(MemoryModel):
    """Hash-protected replay input for a complete append-only episode ledger."""

    schema_version: Literal["1.0"] = "1.0"
    episodes: tuple[Memory, ...]
    retrieval_accesses: tuple[RetrievalAccess, ...]
    reframes: tuple[InterpretationReframe, ...]
    checkpoint_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"checkpoint_sha256"})

    @model_validator(mode="after")
    def validate_hash(self) -> MemoryStoreCheckpoint:
        if self.checkpoint_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("memory-store checkpoint hash mismatch")
        return self

    @classmethod
    def capture(
        cls,
        *,
        episodes: tuple[Memory, ...],
        retrieval_accesses: tuple[RetrievalAccess, ...],
        reframes: tuple[InterpretationReframe, ...],
    ) -> MemoryStoreCheckpoint:
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "episodes": [item.model_dump(mode="json") for item in episodes],
            "retrieval_accesses": [item.model_dump(mode="json") for item in retrieval_accesses],
            "reframes": [item.model_dump(mode="json") for item in reframes],
        }
        payload["checkpoint_sha256"] = sha256_value(payload)
        return cls.model_validate(payload)


class EpisodeStore:
    """Store raw episodes and every later operation as append-only events.

    The object intentionally exposes tuples rather than internal mutable
    collections.  ``get`` derives retrieval counts and the latest
    interpretation without replacing the originally appended episode.
    """

    def __init__(self) -> None:
        self._episodes: tuple[Memory, ...] = ()
        self._retrieval_accesses: tuple[RetrievalAccess, ...] = ()
        self._reframes: tuple[InterpretationReframe, ...] = ()

    @property
    def raw_episodes(self) -> tuple[Memory, ...]:
        return self._episodes

    @property
    def retrieval_accesses(self) -> tuple[RetrievalAccess, ...]:
        return self._retrieval_accesses

    @property
    def reframes(self) -> tuple[InterpretationReframe, ...]:
        return self._reframes

    def append(self, memory: Memory) -> bool:
        """Append one episode, accepting an identical deterministic retry."""

        existing = next(
            (item for item in self._episodes if item.memory_id == memory.memory_id),
            None,
        )
        if existing is not None:
            if existing == memory:
                return False
            raise MemoryStoreError(
                f"memory ID already exists with different evidence: {memory.memory_id}"
            )
        if memory.retrieval_count != 0:
            raise MemoryStoreError("newly appended episodes must start with retrieval_count=0")
        self._episodes = (*self._episodes, memory)
        return True

    def _raw(self, memory_id: str) -> Memory:
        try:
            return next(item for item in self._episodes if item.memory_id == memory_id)
        except StopIteration as exc:
            raise MemoryStoreError(f"unknown memory ID: {memory_id}") from exc

    def get(self, memory_id: str) -> Memory:
        """Return the immutable current view derived from the append-only ledger."""

        raw = self._raw(memory_id)
        interpretation = raw.interpretation
        for event in self._reframes:
            if event.memory_id == memory_id:
                interpretation = event.interpretation
        count = sum(item.memory_id == memory_id for item in self._retrieval_accesses)
        return raw.model_copy(update={"interpretation": interpretation, "retrieval_count": count})

    def all(self) -> tuple[Memory, ...]:
        return tuple(self.get(item.memory_id) for item in self._episodes)

    def record_retrieval(
        self, *, retrieval_id: str, memory_ids: tuple[str, ...], simulation_day: int
    ) -> None:
        """Append idempotent per-memory access events for an audited retrieval."""

        for memory_id in memory_ids:
            self._raw(memory_id)
            access = RetrievalAccess(
                access_id=sha256_value(
                    {
                        "retrieval_id": retrieval_id,
                        "memory_id": memory_id,
                        "simulation_day": simulation_day,
                    }
                ),
                retrieval_id=retrieval_id,
                memory_id=memory_id,
                simulation_day=simulation_day,
            )
            if any(item.access_id == access.access_id for item in self._retrieval_accesses):
                continue
            self._retrieval_accesses = (*self._retrieval_accesses, access)

    def reframe(
        self,
        memory_id: str,
        interpretation: MemoryInterpretation,
        *,
        intervention_id: str,
        reason: str,
    ) -> InterpretationReframe:
        """Append a new interpretation while preserving the raw fact tuple byte-for-byte."""

        current = self.get(memory_id)
        if current.interpretation is None:
            raise MemoryStoreError("cannot reframe an episode without an interpretation")
        fact_ids = {item.fact_id for item in current.observable_facts}
        if not set(interpretation.fact_ids).issubset(fact_ids):
            raise MemoryStoreError("reframed interpretation cites facts outside the episode")
        if interpretation.revision != current.interpretation.revision + 1:
            raise MemoryStoreError("interpretation revision must increment exactly once")
        reframe = InterpretationReframe(
            reframe_id=sha256_value(
                {
                    "memory_id": memory_id,
                    "prior_interpretation_id": current.interpretation.interpretation_id,
                    "interpretation": interpretation.model_dump(mode="json"),
                    "intervention_id": intervention_id,
                    "reason": reason,
                }
            ),
            memory_id=memory_id,
            prior_interpretation_id=current.interpretation.interpretation_id,
            interpretation=interpretation,
            intervention_id=intervention_id,
            reason=reason,
        )
        existing = next(
            (item for item in self._reframes if item.reframe_id == reframe.reframe_id), None
        )
        if existing is not None:
            return existing
        self._reframes = (*self._reframes, reframe)
        return reframe

    def checkpoint(self) -> MemoryStoreCheckpoint:
        return MemoryStoreCheckpoint.capture(
            episodes=self._episodes,
            retrieval_accesses=self._retrieval_accesses,
            reframes=self._reframes,
        )

    @classmethod
    def restore(cls, checkpoint: MemoryStoreCheckpoint) -> EpisodeStore:
        """Replay a validated checkpoint through the same invariants as live writes."""

        store = cls()
        for episode in checkpoint.episodes:
            store.append(episode)
        for access in checkpoint.retrieval_accesses:
            store._raw(access.memory_id)
            if any(item.access_id == access.access_id for item in store._retrieval_accesses):
                raise MemoryStoreError("checkpoint contains duplicate retrieval access IDs")
            store._retrieval_accesses = (*store._retrieval_accesses, access)
        for reframe in checkpoint.reframes:
            current = store.get(reframe.memory_id)
            if current.interpretation is None:
                raise MemoryStoreError("checkpoint reframe has no prior interpretation")
            if reframe.prior_interpretation_id != current.interpretation.interpretation_id:
                raise MemoryStoreError("checkpoint reframe chain is discontinuous")
            fact_ids = {item.fact_id for item in current.observable_facts}
            if not set(reframe.interpretation.fact_ids).issubset(fact_ids):
                raise MemoryStoreError("checkpoint reframe cites facts outside the episode")
            store._reframes = (*store._reframes, reframe)
        return store
