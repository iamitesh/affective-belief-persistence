from __future__ import annotations

import json
from pathlib import Path

import pytest

from affective_belief_persistence.models.base import load_adapter_config
from affective_belief_persistence.models.contracts import AdapterConfig, ProviderKind
from affective_belief_persistence.models.prompt_builder import PromptBundle
from affective_belief_persistence.models.transport import TransportResponse
from affective_belief_persistence.schemas import ActionOption, DecisionRequest


@pytest.fixture
def model_request() -> DecisionRequest:
    return DecisionRequest(
        schema_version="1.0",
        request_id="a" * 64,
        event_id="event-day-01",
        day=1,
        facts=["A scheduled meeting begins at 09:00."],
        action_points=10,
        available_actions=[
            ActionOption(action_id="send-message", description="Send a message.", cost=3),
            ActionOption(action_id="work-alone", description="Continue alone.", cost=1),
        ],
        retrieved_memory_ids=["memory-001"],
        beliefs={"meeting-confirmed": True},
    )


@pytest.fixture
def prompts(project_root: Path) -> PromptBundle:
    return PromptBundle.load(project_root / "prompts/decision", version="decision-v1")


@pytest.fixture
def openai_config(project_root: Path) -> AdapterConfig:
    return load_adapter_config(project_root / "configs/models/openai-compatible-fixture.yaml")


@pytest.fixture
def hf_config(project_root: Path) -> AdapterConfig:
    return load_adapter_config(project_root / "configs/models/hf-local-fixture.yaml")


def action_text(action_id: str = "send-message", cost: int = 3) -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "chosen_action_id": action_id,
            "resources_spent": cost,
            "retrieved_memory_ids": ["memory-001"],
            "belief_updates": [],
            "decision_rationale": "The scheduled meeting supports this allowed action.",
        },
        sort_keys=True,
    )


def language_text() -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "public_response": "I will send the scheduled message.",
        },
        sort_keys=True,
    )


def provider_response(config: AdapterConfig, text: str, *, status: int = 200) -> TransportResponse:
    if config.provider is ProviderKind.OPENAI_COMPATIBLE:
        body = {
            "model": config.model_id,
            "model_revision": config.revision,
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
    else:
        body = {
            "model_id": config.model_id,
            "revision": config.revision,
            "generated_text": text,
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
    return TransportResponse(status_code=status, body=json.dumps(body, sort_keys=True))
