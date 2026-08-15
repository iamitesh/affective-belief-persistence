"""Deterministic consequence application for committed actions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.simulation.actions import ActionCommitment
from affective_belief_persistence.world import Consequence


class ConsequenceError(ValueError):
    """A consequence is missing or violates resource conservation."""


class ConsequenceApplication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    application_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    commitment_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    consequence_id: str = Field(min_length=1)
    resource_delta: int = Field(lt=0)
    goal_progress_delta: dict[str, int]
    emitted_fact_ids: tuple[str, ...] = ()


def apply_consequence(
    commitment: ActionCommitment,
    consequences_by_id: dict[str, Consequence],
) -> ConsequenceApplication:
    """Return the authoritative consequence for an already committed action."""

    try:
        consequence = consequences_by_id[commitment.consequence_id]
    except KeyError as exc:
        raise ConsequenceError(
            f"missing authoritative consequence: {commitment.consequence_id}"
        ) from exc
    if consequence.resource_delta != -commitment.cost:
        raise ConsequenceError("consequence resource delta does not conserve action points")
    payload = {
        "commitment_id": commitment.commitment_id,
        "consequence_id": consequence.consequence_id,
        "resource_delta": consequence.resource_delta,
        "goal_progress_delta": dict(sorted(consequence.goal_progress.items())),
        "emitted_fact_ids": consequence.emitted_fact_ids,
    }
    return ConsequenceApplication(
        application_id=sha256_value(payload),
        commitment_id=commitment.commitment_id,
        consequence_id=consequence.consequence_id,
        resource_delta=consequence.resource_delta,
        goal_progress_delta=dict(sorted(consequence.goal_progress.items())),
        emitted_fact_ids=consequence.emitted_fact_ids,
    )


def update_goal_progress(
    current: dict[str, int], application: ConsequenceApplication
) -> dict[str, int]:
    updated = dict(current)
    for goal_id, delta in application.goal_progress_delta.items():
        updated[goal_id] = updated.get(goal_id, 0) + delta
    return dict(sorted(updated.items()))
