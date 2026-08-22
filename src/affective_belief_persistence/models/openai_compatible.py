"""OpenAI-compatible chat-completions transport adapter."""

from __future__ import annotations

import json
from typing import Any

from affective_belief_persistence.models.base import (
    ExtractedProviderResponse,
    ProviderTwoStageAdapter,
)
from affective_belief_persistence.models.contracts import ProviderKind, TokenUsage
from affective_belief_persistence.models.errors import ProviderResponseError, SafetyPolicyError
from affective_belief_persistence.models.prompt_builder import RenderedPrompt
from affective_belief_persistence.models.transport import TransportRequest, TransportResponse


def _contains_reasoning_metadata(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.casefold().replace("-", "_")
            if normalized in {
                "chain_of_thought",
                "reasoning",
                "reasoning_content",
                "reasoning_tokens",
                "thinking",
            }:
                return True
            if _contains_reasoning_metadata(item):
                return True
    if isinstance(value, list):
        return any(_contains_reasoning_metadata(item) for item in value)
    return False


class OpenAICompatibleAdapter(ProviderTwoStageAdapter):
    """Strict adapter for the common chat-completions JSON transport shape."""

    provider = ProviderKind.OPENAI_COMPATIBLE

    def _build_request(self, prompt: RenderedPrompt, *, seed: int) -> TransportRequest:
        endpoint = self.config.endpoint
        if endpoint is None:  # guarded by AdapterConfig; keeps type narrowing explicit
            raise ValueError("OpenAI-compatible endpoint is required")
        body: dict[str, object] = {
            "model": self.model_id,
            "model_revision": self.revision,
            "messages": [{"role": "user", "content": prompt.text}],
            "temperature": self.config.inference.temperature,
            "top_p": self.config.inference.top_p,
            "max_tokens": self.config.inference.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if self.config.inference.seed_supported:
            body["seed"] = seed
        return TransportRequest(
            url=str(endpoint),
            headers={"Content-Type": "application/json"},
            json_body=body,
        )

    def _extract_response(self, response: TransportResponse) -> ExtractedProviderResponse:
        try:
            payload: Any = json.loads(response.body)
            if not isinstance(payload, dict):
                raise TypeError("provider envelope must be an object")
            if _contains_reasoning_metadata(payload):
                raise SafetyPolicyError("provider envelope exposed hidden-reasoning metadata")
            choices = payload["choices"]
            choice = choices[0]
            content = choice["message"]["content"]
            model_id = payload["model"]
            revision = payload["model_revision"]
            usage_payload = payload.get("usage", {})
            usage = TokenUsage(
                input_tokens=int(usage_payload.get("prompt_tokens", 0)),
                output_tokens=int(usage_payload.get("completion_tokens", 0)),
            )
        except SafetyPolicyError:
            raise
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderResponseError(
                f"invalid OpenAI-compatible response envelope: {exc}"
            ) from exc
        if not all(isinstance(value, str) for value in (content, model_id, revision)):
            raise ProviderResponseError("provider text and identity fields must be strings")
        return ExtractedProviderResponse(
            text=content,
            model_id=model_id,
            revision=revision,
            usage=usage,
        )
