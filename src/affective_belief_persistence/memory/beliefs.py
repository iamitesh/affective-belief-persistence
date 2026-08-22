"""Evidence-linked, append-only relationship belief ledger."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.contracts import Belief, MemoryModel, Sha256
from affective_belief_persistence.memory.store import EpisodeStore, MemoryStoreError


class BeliefError(ValueError):
    """A belief update lacks valid evidence or breaks ledger ordering."""


class BeliefCheckpoint(MemoryModel):
    schema_version: Literal["1.0"] = "1.0"
    versions: tuple[Belief, ...]
    checkpoint_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"checkpoint_sha256"})

    @model_validator(mode="after")
    def validate_hash(self) -> BeliefCheckpoint:
        if self.checkpoint_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("belief checkpoint hash mismatch")
        return self

    @classmethod
    def capture(cls, versions: tuple[Belief, ...]) -> BeliefCheckpoint:
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "versions": [item.model_dump(mode="json") for item in versions],
        }
        payload["checkpoint_sha256"] = sha256_value(payload)
        return cls.model_validate(payload)


class BeliefLedger:
    """Append-only versions with evidence integrity checked against episode storage."""

    def __init__(self, store: EpisodeStore) -> None:
        self.store = store
        self._versions: tuple[Belief, ...] = ()

    @property
    def versions(self) -> tuple[Belief, ...]:
        return self._versions

    def current(self, belief_id: str) -> Belief | None:
        return next(
            (item for item in reversed(self._versions) if item.belief_id == belief_id), None
        )

    def append(self, belief: Belief) -> bool:
        evidence_ids = (
            *belief.supporting_evidence_ids,
            *belief.contradicting_evidence_ids,
        )
        try:
            for memory_id in evidence_ids:
                self.store.get(memory_id)
        except MemoryStoreError as exc:
            raise BeliefError(f"belief cites unknown evidence: {exc}") from exc

        previous = self.current(belief.belief_id)
        if previous is not None:
            if previous == belief:
                return False
            if belief.last_update_day < previous.last_update_day:
                raise BeliefError("belief updates cannot move backward in simulated time")
            if not set(previous.supporting_evidence_ids).issubset(
                belief.supporting_evidence_ids
            ) or not set(previous.contradicting_evidence_ids).issubset(
                belief.contradicting_evidence_ids
            ):
                raise BeliefError("belief updates cannot discard cited evidence")
        self._versions = (*self._versions, belief)
        return True

    def checkpoint(self) -> BeliefCheckpoint:
        return BeliefCheckpoint.capture(self._versions)

    @classmethod
    def restore(cls, store: EpisodeStore, checkpoint: BeliefCheckpoint) -> BeliefLedger:
        ledger = cls(store)
        for belief in checkpoint.versions:
            ledger.append(belief)
        return ledger
