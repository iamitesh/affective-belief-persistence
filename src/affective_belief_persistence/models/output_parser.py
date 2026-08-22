"""Strict JSON parsing and simulation-contract validation."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import ValidationError

from affective_belief_persistence.models.contracts import (
    ActionOutput,
    ModelInput,
    PublicLanguageOutput,
    RunnerModel,
)
from affective_belief_persistence.models.errors import (
    CostMismatchError,
    InvalidActionError,
    InvalidJSONError,
    OutputSchemaError,
    SafetyPolicyError,
    UnknownMemoryReferenceError,
)

OutputT = TypeVar("OutputT", bound=RunnerModel)

_PRIVATE_OUTPUT_MARKER = re.compile(
    r"(?i)\b(?:BEGIN PRIVATE REASONING|hidden chain[- ]of[- ]thought\s*:|"
    r"private scratchpad\s*:)"
)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidJSONError(f"model output is not strict JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidJSONError("model output must be one JSON object")
    return value


def _validate_model(raw: str, model: type[OutputT]) -> OutputT:
    payload = _load_json_object(raw)
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise OutputSchemaError(f"model output failed schema validation: {exc}") from exc


def _validate_release_text(text: str) -> None:
    if _PRIVATE_OUTPUT_MARKER.search(text):
        raise SafetyPolicyError("model output contains a prohibited private-reasoning marker")


def parse_action_output(raw: str, model_input: ModelInput) -> ActionOutput:
    """Parse an action and prove IDs/costs are constrained by the input menu."""

    output = _validate_model(raw, ActionOutput)
    actions = {action.action_id: action for action in model_input.allowed_actions}
    try:
        selected = actions[output.chosen_action_id]
    except KeyError as exc:
        raise InvalidActionError(
            f"chosen action is not in the supplied menu: {output.chosen_action_id}"
        ) from exc
    if output.resources_spent != selected.cost:
        raise CostMismatchError("resources_spent does not match the selected action's frozen cost")
    if len(output.retrieved_memory_ids) != len(set(output.retrieved_memory_ids)):
        raise UnknownMemoryReferenceError("retrieved memory IDs must be unique")
    available_memory_ids = {memory.memory_id for memory in model_input.retrieved_memories}
    unknown_memories = set(output.retrieved_memory_ids) - available_memory_ids
    if unknown_memories:
        raise UnknownMemoryReferenceError(
            "output cites memory IDs absent from the retrieved-memory input"
        )
    evidence_ids = {model_input.event_id, *available_memory_ids}
    for memory in model_input.retrieved_memories:
        evidence_ids.update(memory.source_ids)
    for update in output.belief_updates:
        if not set(update.evidence_ids).issubset(evidence_ids):
            raise UnknownMemoryReferenceError(
                "belief update cites evidence IDs absent from the model input"
            )
    if output.decision_rationale is not None:
        _validate_release_text(output.decision_rationale)
    return output


def parse_public_language_output(raw: str) -> PublicLanguageOutput:
    """Parse language only; any attempted action field is a schema violation."""

    output = _validate_model(raw, PublicLanguageOutput)
    _validate_release_text(output.public_response)
    return output
