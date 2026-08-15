"""Append-only event records for auditable orchestration state changes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from affective_belief_persistence.orchestration.contracts import (
    Identifier,
    OrchestrationModel,
    Scalar,
    TaskStatus,
)


class WorkflowEventType(StrEnum):
    """Kinds of facts that may be appended to a workflow history."""

    WORKFLOW_CREATED = "workflow_created"
    STATUS_TRANSITION = "status_transition"
    ARTIFACT_REGISTERED = "artifact_registered"
    HANDOFF_REGISTERED = "handoff_registered"
    CHECKPOINT_SAVED = "checkpoint_saved"
    SAFETY_BOUNDARY_DETECTED = "safety_boundary_detected"
    SAFETY_ACTION_APPLIED = "safety_action_applied"
    SAFETY_RESOLVED = "safety_resolved"
    NOTE = "note"


class WorkflowEvent(OrchestrationModel):
    """One immutable event; sequence is monotonic within a workflow."""

    event_id: Identifier
    workflow_id: Identifier
    sequence: int = Field(ge=1)
    event_type: WorkflowEventType
    occurred_at: datetime
    actor_id: Identifier
    task_id: Identifier | None = None
    previous_status: TaskStatus | None = None
    new_status: TaskStatus | None = None
    message: str | None = Field(default=None, min_length=1)
    payload: dict[str, Scalar] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_transition_payload(self) -> WorkflowEvent:
        statuses = (self.previous_status, self.new_status)
        if self.event_type is WorkflowEventType.STATUS_TRANSITION:
            if self.task_id is None or any(status is None for status in statuses):
                raise ValueError("status transition events require task and both statuses")
        elif any(status is not None for status in statuses):
            raise ValueError("status fields are reserved for status transition events")
        if self.event_type in {
            WorkflowEventType.SAFETY_BOUNDARY_DETECTED,
            WorkflowEventType.SAFETY_ACTION_APPLIED,
            WorkflowEventType.SAFETY_RESOLVED,
        }:
            required = {"safety_event_id", "condition_id", "severity", "primary_action"}
            missing = required - self.payload.keys()
            if self.task_id is None or missing:
                details = ", ".join(sorted(missing)) or "task_id"
                raise ValueError(f"safety events require task_id and payload fields: {details}")
        return self


class EventLog(OrchestrationModel):
    """Persistent append-only workflow event sequence.

    ``append`` returns a new log, which prevents in-place history rewrites and
    makes the object safe to place directly inside a checkpoint.
    """

    workflow_id: Identifier
    events: tuple[WorkflowEvent, ...] = ()

    @model_validator(mode="after")
    def validate_history(self) -> EventLog:
        seen: set[str] = set()
        previous_time: datetime | None = None
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.workflow_id != self.workflow_id:
                raise ValueError("every event must belong to the log workflow")
            if event.sequence != expected_sequence:
                raise ValueError("event sequences must be contiguous and start at one")
            if event.event_id in seen:
                raise ValueError("event IDs must be unique within a workflow")
            if previous_time is not None and event.occurred_at < previous_time:
                raise ValueError("event timestamps must be monotonic")
            seen.add(event.event_id)
            previous_time = event.occurred_at
        return self

    @property
    def next_sequence(self) -> int:
        return len(self.events) + 1

    def append(self, event: WorkflowEvent) -> EventLog:
        """Return a new log with ``event`` appended after strict ordering checks."""

        if event.workflow_id != self.workflow_id:
            raise ValueError("cannot append an event for another workflow")
        if event.sequence != self.next_sequence:
            raise ValueError(f"next event sequence must be {self.next_sequence}")
        if any(existing.event_id == event.event_id for existing in self.events):
            raise ValueError(f"duplicate event ID: {event.event_id}")
        if self.events and event.occurred_at < self.events[-1].occurred_at:
            raise ValueError("event timestamps must be monotonic")
        return self.model_copy(update={"events": (*self.events, event)})
