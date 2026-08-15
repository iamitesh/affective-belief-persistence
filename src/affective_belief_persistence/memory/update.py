"""Declared deterministic and validated-proposal belief update boundaries."""

from __future__ import annotations

from pydantic import Field

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.contracts import Belief, MemoryModel


def initial_belief(*, relationship_id: str, belief_id: str | None = None) -> Belief:
    """Create an explicit unknown state; absence of evidence is not negative evidence."""

    return Belief(
        belief_id=belief_id or f"belief-{relationship_id}",
        relationship_id=relationship_id,
        relationship_active=None,
        relationship_romantic=None,
        relationship_reciprocal=None,
        partner_reliability=0.5,
        expected_future_interaction=0.5,
        confidence=0.0,
        supporting_evidence_ids=(),
        contradicting_evidence_ids=(),
        last_update_day=0,
        update_source="deterministic_evidence",
    )


def update_belief_evidence(
    belief: Belief,
    *,
    simulation_day: int,
    supporting_memory_ids: tuple[str, ...] = (),
    contradicting_memory_ids: tuple[str, ...] = (),
) -> Belief:
    """Link evidence deterministically without inventing proposition semantics.

    The generic world evidence is about a ``relationship-interpretation``.  It
    does not alone establish romance, reciprocity, or subjective state, so this
    update changes evidence and bounded confidence while leaving those explicit
    proposition fields unchanged.
    """

    support = tuple(sorted(set(belief.supporting_evidence_ids) | set(supporting_memory_ids)))
    contradict = tuple(
        sorted(set(belief.contradicting_evidence_ids) | set(contradicting_memory_ids))
    )
    if set(support) & set(contradict):
        raise ValueError("one memory cannot both support and contradict the same belief")
    total = len(support) + len(contradict)
    confidence = 0.0 if total == 0 else abs(len(support) - len(contradict)) / total
    return belief.model_copy(
        update={
            "supporting_evidence_ids": support,
            "contradicting_evidence_ids": contradict,
            "confidence": confidence,
            "last_update_day": simulation_day,
            "update_source": "deterministic_evidence",
        }
    )


class BeliefProposal(MemoryModel):
    """Structured model proposal; explanatory chain-of-thought has no field."""

    proposal_id: str = Field(min_length=1)
    relationship_active: bool | None
    relationship_romantic: bool | None
    relationship_reciprocal: bool | None
    partner_reliability: float = Field(ge=0, le=1)
    expected_future_interaction: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]

    @classmethod
    def create(cls, **values: object) -> BeliefProposal:
        proposal_id = sha256_value(values)
        return cls.model_validate({"proposal_id": proposal_id, **values})


def accept_validated_proposal(
    current: Belief,
    proposal: BeliefProposal,
    *,
    simulation_day: int,
) -> Belief:
    """Accept only an evidence-linked, bounded structured proposal."""

    if set(proposal.supporting_evidence_ids) & set(proposal.contradicting_evidence_ids):
        raise ValueError("proposal evidence directions must be disjoint")
    if not proposal.supporting_evidence_ids and not proposal.contradicting_evidence_ids:
        raise ValueError("model-proposed belief updates require cited evidence")
    return Belief(
        belief_id=current.belief_id,
        relationship_id=current.relationship_id,
        relationship_active=proposal.relationship_active,
        relationship_romantic=proposal.relationship_romantic,
        relationship_reciprocal=proposal.relationship_reciprocal,
        partner_reliability=proposal.partner_reliability,
        expected_future_interaction=proposal.expected_future_interaction,
        confidence=proposal.confidence,
        supporting_evidence_ids=tuple(sorted(proposal.supporting_evidence_ids)),
        contradicting_evidence_ids=tuple(sorted(proposal.contradicting_evidence_ids)),
        last_update_day=simulation_day,
        update_source="validated_model_proposal",
    )
