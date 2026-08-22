from __future__ import annotations

import json
from pathlib import Path

import pytest

from affective_belief_persistence.models.cache import (
    SafeResponseCache,
    SyntheticFixtureRetentionPolicy,
)
from affective_belief_persistence.models.contracts import CacheSettings, ModelStage, ProviderKind
from affective_belief_persistence.models.errors import (
    CacheCorruptionError,
    CostMismatchError,
    InvalidActionError,
    InvalidRunError,
    ModelIdentityError,
    RetryExhaustedError,
    SafetyPolicyError,
)
from affective_belief_persistence.models.hf_local import HFLocalHTTPAdapter
from affective_belief_persistence.models.openai_compatible import OpenAICompatibleAdapter
from affective_belief_persistence.models.prompt_builder import PromptBundle
from affective_belief_persistence.models.transport import (
    ScriptedTransport,
    TransportResponse,
)
from affective_belief_persistence.schemas import DecisionRequest, ModelConfig

from .conftest import action_text, language_text, provider_response


def _adapter_type(provider: ProviderKind):
    if provider is ProviderKind.OPENAI_COMPATIBLE:
        return OpenAICompatibleAdapter
    return HFLocalHTTPAdapter


@pytest.mark.parametrize("config_fixture", ["openai_config", "hf_config"])
def test_cross_adapter_action_first_smoke_matrix(
    request,
    config_fixture: str,
    prompts: PromptBundle,
    model_request: DecisionRequest,
) -> None:
    config = request.getfixturevalue(config_fixture)
    transport = ScriptedTransport(
        [provider_response(config, action_text()), provider_response(config, language_text())]
    )
    adapter = _adapter_type(config.provider)(config, transport=transport, prompts=prompts)

    selection = adapter.select_action(model_request, seed=42)
    public_response = adapter.generate_public_language(
        model_request,
        selection,
        action_commitment_sha256="c" * 64,
        seed=84,
    )

    assert selection.chosen_action == "send-message"
    assert selection.resources_spent == 3
    assert public_response == "I will send the scheduled message."
    assert [record.provenance.stage for record in adapter.invocations] == [
        ModelStage.ACTION,
        ModelStage.PUBLIC_LANGUAGE,
    ]
    assert all(record.provenance.model_id == config.model_id for record in adapter.invocations)
    assert all(record.provenance.revision == config.revision for record in adapter.invocations)
    assert all(
        record.provenance.run_id == adapter.invocations[0].provenance.run_id
        for record in adapter.invocations
    )
    requested_model = transport.requests[0].json_body.get(
        "model", transport.requests[0].json_body.get("model_id")
    )
    assert requested_model == config.model_id


@pytest.mark.parametrize("config_fixture", ["openai_config", "hf_config"])
def test_one_deterministic_malformed_output_repair(
    request,
    config_fixture: str,
    prompts: PromptBundle,
    model_request: DecisionRequest,
) -> None:
    config = request.getfixturevalue(config_fixture)
    transport = ScriptedTransport(
        [provider_response(config, "not-json"), provider_response(config, action_text())]
    )
    adapter = _adapter_type(config.provider)(config, transport=transport, prompts=prompts)

    selection = adapter.select_action(model_request, seed=42)

    assert selection.chosen_action == "send-message"
    assert len(transport.requests) == 2
    assert adapter.invocations[-1].provenance.stage is ModelStage.ACTION_REPAIR
    assert adapter.invocations[-1].provenance.repair_attempt is True


def test_unrepaired_output_is_categorized_invalid_run(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    transport = ScriptedTransport(
        [
            provider_response(openai_config, "not-json"),
            provider_response(openai_config, "still-bad"),
        ]
    )
    adapter = OpenAICompatibleAdapter(openai_config, transport=transport, prompts=prompts)

    with pytest.raises(InvalidRunError) as caught:
        adapter.select_action(model_request, seed=42)

    assert caught.value.cause_category is not None
    assert len(transport.requests) == 2


@pytest.mark.parametrize(
    ("output", "error_type"),
    [
        (action_text("unknown", 3), InvalidActionError),
        (action_text("send-message", 1), CostMismatchError),
    ],
)
def test_semantic_contract_failure_does_not_invent_or_repair_action(
    output: str,
    error_type: type[Exception],
    openai_config,
    prompts: PromptBundle,
    model_request: DecisionRequest,
) -> None:
    transport = ScriptedTransport([provider_response(openai_config, output)])
    adapter = OpenAICompatibleAdapter(openai_config, transport=transport, prompts=prompts)
    with pytest.raises(error_type):
        adapter.select_action(model_request, seed=42)
    assert len(transport.requests) == 1


def test_timeout_and_rate_limit_are_normalized_and_bounded(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    transport = ScriptedTransport(
        [
            TimeoutError("fixture timeout"),
            provider_response(openai_config, action_text()),
        ]
    )
    adapter = OpenAICompatibleAdapter(openai_config, transport=transport, prompts=prompts)
    assert adapter.select_action(model_request, seed=42).chosen_action == "send-message"
    assert adapter.invocations[0].failure_category == "timeout"

    limited = ScriptedTransport(
        [
            TransportResponse(status_code=429, body='{"error":"limited"}'),
            provider_response(openai_config, action_text()),
        ]
    )
    adapter = OpenAICompatibleAdapter(openai_config, transport=limited, prompts=prompts)
    assert adapter.select_action(model_request, seed=42).chosen_action == "send-message"
    assert adapter.invocations[0].failure_category == "rate_limit"


def test_retry_exhaustion_reports_original_category(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    adapter = OpenAICompatibleAdapter(
        openai_config,
        transport=ScriptedTransport([TimeoutError(), TimeoutError()]),
        prompts=prompts,
    )
    with pytest.raises(RetryExhaustedError) as caught:
        adapter.select_action(model_request, seed=42)
    assert caught.value.cause_category is not None
    assert caught.value.cause_category.value == "timeout"


def test_response_identity_mismatch_never_falls_back(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    response = json.loads(provider_response(openai_config, action_text()).body)
    response["model"] = "undeclared-substitute"
    transport = ScriptedTransport([TransportResponse(status_code=200, body=json.dumps(response))])
    adapter = OpenAICompatibleAdapter(openai_config, transport=transport, prompts=prompts)
    with pytest.raises(ModelIdentityError):
        adapter.select_action(model_request, seed=42)
    assert len(transport.requests) == 1


def test_hidden_reasoning_metadata_is_hashed_but_never_retained(
    openai_config, prompts: PromptBundle, model_request: DecisionRequest
) -> None:
    response = json.loads(provider_response(openai_config, action_text()).body)
    response["reasoning"] = "private provider trace"
    transport = ScriptedTransport([TransportResponse(status_code=200, body=json.dumps(response))])
    adapter = OpenAICompatibleAdapter(
        openai_config,
        transport=transport,
        prompts=prompts,
        retention_policy=SyntheticFixtureRetentionPolicy(),
    )
    with pytest.raises(SafetyPolicyError):
        adapter.select_action(model_request, seed=42)
    record = adapter.invocations[0]
    assert record.failure_category == "safety_policy_blocked"
    assert record.response_sha256 is not None
    assert record.raw_response_retained is False
    assert record.raw_response is None


def test_safe_cache_replays_without_transport_regeneration(
    tmp_path: Path,
    openai_config,
    prompts: PromptBundle,
    model_request: DecisionRequest,
) -> None:
    config = openai_config.model_copy(
        update={
            "cache": CacheSettings(
                enabled=True,
                directory=str(tmp_path / "cache"),
                preserve_raw_responses=True,
            )
        }
    )
    cache = SafeResponseCache(tmp_path / "cache")
    policy = SyntheticFixtureRetentionPolicy()
    first_transport = ScriptedTransport([provider_response(config, action_text())])
    first = OpenAICompatibleAdapter(
        config,
        transport=first_transport,
        prompts=prompts,
        cache=cache,
        retention_policy=policy,
    )
    first_selection = first.select_action(model_request, seed=42)

    offline_transport = ScriptedTransport([])
    replay = OpenAICompatibleAdapter(
        config,
        transport=offline_transport,
        prompts=prompts,
        cache=cache,
        retention_policy=policy,
    )
    replay_selection = replay.select_action(model_request, seed=42)

    assert replay_selection == first_selection
    assert offline_transport.requests == []
    assert replay.invocations[0].provenance.cache_hit is True
    assert replay.invocations[0].raw_response_retained is True


def test_cache_entries_are_immutable(tmp_path: Path) -> None:
    cache = SafeResponseCache(tmp_path / "cache")
    policy = SyntheticFixtureRetentionPolicy()
    key = cache.make_key({"request": "fixed"})
    assert cache.put(key, status_code=200, body='{"first":true}', retention_policy=policy)
    assert cache.put(key, status_code=200, body='{"first":true}', retention_policy=policy)
    with pytest.raises(CacheCorruptionError):
        cache.put(key, status_code=200, body='{"second":true}', retention_policy=policy)


def test_legacy_mock_now_satisfies_two_stage_contract(
    project_root: Path, model_request: DecisionRequest
) -> None:
    payload = {
        "schema_version": "1.0",
        "provider": "mock",
        "model_id": "deterministic-mock",
        "revision": "mock-v1",
        "temperature": 0.0,
        "max_output_tokens": 256,
    }
    config = ModelConfig.model_validate(payload)
    from affective_belief_persistence.models.mock import DeterministicMockModel

    first = DeterministicMockModel(config).select_action(model_request, seed=42)
    second = DeterministicMockModel(config).select_action(model_request, seed=42)
    assert first == second
    assert (
        DeterministicMockModel(config)
        .generate_public_language(
            model_request,
            first,
            action_commitment_sha256="c" * 64,
            seed=84,
        )
        .startswith("Mock decision:")
    )
    assert (project_root / "configs/models/mock.yaml").is_file()
