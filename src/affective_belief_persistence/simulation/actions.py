"""Action-first decision validation and immutable action commitments."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.simulation.model import ActionSelection
from affective_belief_persistence.world import ActionOption, Event


class ActionSelectionError(ValueError):
    """A model decision cannot be committed to the controlled action menu."""


class ActionCommitment(BaseModel):
    """Validated action data, deliberately excluding public language."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commitment_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_id: str = Field(min_length=1)
    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_id: str = Field(min_length=1)
    consequence_id: str = Field(min_length=1)
    cost: int = Field(gt=0)


def commit_action(
    event: Event,
    actions_by_id: dict[str, ActionOption],
    decision: ActionSelection,
) -> ActionCommitment:
    """Validate and commit the structured action before exposing model language."""

    if decision.chosen_action not in event.available_action_ids:
        raise ActionSelectionError(
            f"model selected action unavailable for {event.event_id}: {decision.chosen_action}"
        )
    try:
        action = actions_by_id[decision.chosen_action]
    except KeyError as exc:
        message = f"model selected unknown action: {decision.chosen_action}"
        raise ActionSelectionError(message) from exc
    if decision.resources_spent != action.cost:
        raise ActionSelectionError(
            "model resources_spent must exactly equal the authoritative action cost"
        )
    if action.cost <= 0:
        raise ActionSelectionError("simulation actions must have a positive cost")
    if action.consequence_id not in event.consequence_ids:
        raise ActionSelectionError("selected action consequence is not available for this event")
    payload = {
        "action_id": action.action_id,
        "consequence_id": action.consequence_id,
        "cost": action.cost,
        "decision_id": decision.decision_id,
        "event_id": event.event_id,
    }
    return ActionCommitment(
        commitment_id=sha256_value(payload),
        event_id=event.event_id,
        decision_id=decision.decision_id,
        action_id=action.action_id,
        consequence_id=action.consequence_id,
        cost=action.cost,
    )
