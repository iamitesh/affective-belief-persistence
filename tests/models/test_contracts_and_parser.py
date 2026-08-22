from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.models.base import load_adapter_config
from affective_belief_persistence.models.contracts import MODEL_RUNNER_SCHEMA_MODELS
from affective_belief_persistence.models.errors import (
    CostMismatchError,
    InvalidActionError,
    InvalidJSONError,
    OutputSchemaError,
)
from affective_belief_persistence.models.openai_compatible import OpenAICompatibleAdapter
from affective_belief_persistence.models.output_parser import (
    parse_action_output,
    parse_public_language_output,
)
from affective_belief_persistence.models.prompt_builder import PromptBundle, PromptError
from affective_belief_persistence.models.transport import ScriptedTransport
from affective_belief_persistence.schemas import DecisionRequest


def test_sidecar_configs_are_strict_and_preserve_frozen_mock(project_root: Path) -> None:
    configs = [
        load_adapter_config(project_root / "configs/models/mock-runner.yaml"),
        load_adapter_config(project_root / "configs/models/openai-compatible-fixture.yaml"),
        load_adapter_config(project_root / "configs/models/hf-local-fixture.yaml"),
    ]
    assert [item.provider.value for item in configs] == [
        "mock",
        "openai_compatible",
        "hf_local_http",
    ]
    assert all(item.live_calls_enabled is False for item in configs)
    assert (
        (project_root / "configs/models/mock.yaml")
        .read_text(encoding="utf-8")
        .startswith('schema_version: "1.0"')
    )


def test_cycle_safe_schema_map_has_all_runner_boundaries() -> None:
    assert set(MODEL_RUNNER_SCHEMA_MODELS) == {
        "model-input.schema.json",
        "model-action-output.schema.json",
        "public-language-output.schema.json",
        "model-invocation-record.schema.json",
    }
    for model in MODEL_RUNNER_SCHEMA_MODELS.values():
        assert model.model_json_schema()["additionalProperties"] is False


def test_input_bridge_captures_issue9_fields(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    adapter = OpenAICompatibleAdapter(
        openai_config,
        transport=ScriptedTransport([]),
        prompts=prompts,
    )
    model_input = adapter.input_from_request(model_request)
    assert model_input.phase.value == "baseline"
    assert model_input.resources.available == 10
    assert [action.action_id for action in model_input.allowed_actions] == [
        "send-message",
        "work-alone",
    ]
    assert model_input.retrieved_memories[0].memory_id == "memory-001"
    assert model_input.current_beliefs[0].belief_id == "meeting-confirmed"


def test_parser_rejects_invalid_action_cost_and_non_json(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    adapter = OpenAICompatibleAdapter(
        openai_config,
        transport=ScriptedTransport([]),
        prompts=prompts,
    )
    model_input = adapter.input_from_request(model_request)
    base = {
        "schema_version": "1.0",
        "retrieved_memory_ids": [],
        "belief_updates": [],
    }
    with pytest.raises(InvalidActionError):
        parse_action_output(
            json.dumps({**base, "chosen_action_id": "not-allowed", "resources_spent": 3}),
            model_input,
        )
    with pytest.raises(CostMismatchError):
        parse_action_output(
            json.dumps({**base, "chosen_action_id": "send-message", "resources_spent": 1}),
            model_input,
        )
    with pytest.raises(InvalidJSONError):
        parse_action_output("```json\n{}\n```", model_input)


def test_language_contract_cannot_modify_committed_action() -> None:
    with pytest.raises(OutputSchemaError):
        parse_public_language_output(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "public_response": "I changed my choice.",
                    "chosen_action_id": "work-alone",
                }
            )
        )


def test_prompt_bundle_never_requests_private_reasoning(project_root: Path) -> None:
    bundle = PromptBundle.load(project_root / "prompts/decision", version="decision-v1")
    joined = "\n".join((bundle.action, bundle.language, bundle.repair)).casefold()
    assert "step by step" not in joined
    assert "show your work" not in joined
    assert "chain-of-thought" not in joined
    with pytest.raises(PromptError):
        PromptBundle(
            version="unsafe",
            action="Provide your private reasoning and return JSON.",
            language="Return JSON.",
            repair="Repair JSON.",
        )


def test_config_rejects_undeclared_fallback(openai_config) -> None:
    payload = openai_config.model_dump(mode="json")
    payload["fallback_model_id"] = "silent-substitute"
    with pytest.raises(ValidationError):
        type(openai_config).model_validate(payload)
