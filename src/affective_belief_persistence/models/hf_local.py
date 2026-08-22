"""Hugging Face/local text-generation HTTP transport adapter."""

from __future__ import annotations

import json
from typing import Any

from affective_belief_persistence.models.base import (
    ExtractedProviderResponse,
    ProviderTwoStageAdapter,
)
from affective_belief_persistence.models.contracts import ProviderKind, TokenUsage
from affective_belief_persistence.models.errors import ProviderResponseError, SafetyPolicyError
from affective_belief_persistence.models.openai_compatible import _contains_reasoning_metadata
from affective_belief_persistence.models.prompt_builder import RenderedPrompt
from affective_belief_persistence.models.transport import TransportRequest, TransportResponse


class HFLocalHTTPAdapter(ProviderTwoStageAdapter):
    """Strict local/HF-family adapter requiring a pinned model revision response."""

    provider = ProviderKind.HF_LOCAL_HTTP

    def _build_request(self, prompt: RenderedPrompt, *, seed: int) -> TransportRequest:
        endpoint = self.config.endpoint
        if endpoint is None:  # guarded by AdapterConfig; keeps type narrowing explicit
            raise ValueError("local/HF endpoint is required")
        parameters: dict[str, object] = {
            "do_sample": self.config.inference.temperature > 0,
            "max_new_tokens": self.config.inference.max_output_tokens,
            "return_full_text": False,
            "temperature": self.config.inference.temperature,
            "top_p": self.config.inference.top_p,
        }
        if self.config.inference.seed_supported:
            parameters["seed"] = seed
        return TransportRequest(
            url=str(endpoint),
            headers={"Content-Type": "application/json"},
            json_body={
                "inputs": prompt.text,
                "model_id": self.model_id,
                "revision": self.revision,
                "parameters": parameters,
            },
        )

    def _extract_response(self, response: TransportResponse) -> ExtractedProviderResponse:
        try:
            payload: Any = json.loads(response.body)
            if not isinstance(payload, dict):
                raise TypeError("provider envelope must be an object")
            if _contains_reasoning_metadata(payload):
                raise SafetyPolicyError("provider envelope exposed hidden-reasoning metadata")
            content = payload["generated_text"]
            model_id = payload["model_id"]
            revision = payload["revision"]
            usage_payload = payload.get("usage", {})
            usage = TokenUsage(
                input_tokens=int(usage_payload.get("input_tokens", 0)),
                output_tokens=int(usage_payload.get("output_tokens", 0)),
            )
        except SafetyPolicyError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderResponseError(f"invalid local/HF response envelope: {exc}") from exc
        if not all(isinstance(value, str) for value in (content, model_id, revision)):
            raise ProviderResponseError("provider text and identity fields must be strings")
        return ExtractedProviderResponse(
            text=content,
            model_id=model_id,
            revision=revision,
            usage=usage,
        )
