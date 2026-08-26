"""Fail-closed offline boundary for a future revision-stamping vLLM gateway.

This module deliberately constructs no HTTP client or server. The gateway can
wrap only an injected non-live transport, which lets CI verify request filtering
and response stamping without creating a path to an external model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from affective_belief_persistence.config import ConfigError, load_yaml
from affective_belief_persistence.determinism import canonical_json, sha256_file, sha256_value
from affective_belief_persistence.gate3.contracts import (
    CheckStatus,
    GatewayDeploymentManifest,
    GatewayMetadataSnapshot,
    GatewayProbeResult,
    PreflightCheck,
)
from affective_belief_persistence.models.base import load_adapter_config
from affective_belief_persistence.models.errors import (
    ModelIdentityError,
    ProviderRequestError,
    ProviderResponseError,
    SafetyPolicyError,
)
from affective_belief_persistence.models.transport import (
    ModelTransport,
    TransportRequest,
    TransportResponse,
)

_ALLOWED_REQUEST_FIELDS = frozenset(
    {
        "model",
        "model_revision",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "response_format",
        "seed",
        "stream",
    }
)
_REASONING_FIELDS = frozenset(
    {"chain_of_thought", "reasoning", "reasoning_content", "reasoning_tokens", "thinking"}
)


def load_gateway_manifest(path: Path, *, project_root: Path) -> GatewayDeploymentManifest:
    """Load only a regular repository file under ``configs/gate3``."""

    root = project_root.resolve()
    allowed = (root / "configs/gate3").resolve()
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(allowed) or not resolved.is_file():
        raise ValueError("gateway manifest must be a regular file under configs/gate3")
    try:
        manifest = GatewayDeploymentManifest.model_validate(load_yaml(resolved))
        adapter_path = root / manifest.adapter_config_path
        if (
            adapter_path.is_symlink()
            or not adapter_path.resolve().is_relative_to(root)
            or not adapter_path.resolve().is_file()
            or sha256_file(adapter_path.resolve()) != manifest.adapter_config_sha256
        ):
            raise ValueError("gateway adapter config bytes do not match the manifest")
        adapter = load_adapter_config(adapter_path.resolve())
        if (
            adapter.model_id != manifest.model_id
            or adapter.revision != manifest.revision
            or str(adapter.endpoint) != str(manifest.gateway_endpoint)
            or adapter.live_calls_enabled
        ):
            raise ValueError("gateway adapter identity or non-live state does not match")
        return manifest
    except (ConfigError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid gateway manifest {path}: {exc}") from exc


def _check(check_id: str, passed: bool, detail: str) -> PreflightCheck:
    return PreflightCheck(
        check_id=check_id,
        status=CheckStatus.PASSED if passed else CheckStatus.BLOCKED,
        detail=detail,
    )


def probe_gateway_identity(
    manifest: GatewayDeploymentManifest,
    snapshot: GatewayMetadataSnapshot | None,
    *,
    manifest_sha256: str | None = None,
) -> GatewayProbeResult:
    """Compare injected metadata to the manifest without generating model output."""

    runtime = manifest.runtime
    checks = (
        _check(
            "runtime-identity-resolved",
            runtime.resolved,
            "vLLM version, image digest, launch arguments and code commit must be pinned",
        ),
        _check(
            "metadata-snapshot-present",
            snapshot is not None,
            "a metadata-only runtime snapshot is required",
        ),
        _check(
            "metadata-model-matches",
            snapshot is not None and manifest.model_id in snapshot.model_ids,
            "metadata must expose the exact manifest model ID",
        ),
        _check(
            "metadata-vllm-version-matches",
            snapshot is not None
            and runtime.vllm_version is not None
            and snapshot.vllm_version == runtime.vllm_version,
            "metadata vLLM version must match the deployment manifest",
        ),
        _check(
            "metadata-image-digest-matches",
            snapshot is not None
            and runtime.runtime_image_digest is not None
            and snapshot.runtime_image_digest == runtime.runtime_image_digest,
            "metadata runtime image digest must match the deployment manifest",
        ),
        _check(
            "metadata-code-commit-matches",
            snapshot is not None
            and runtime.code_commit_sha is not None
            and snapshot.deployment_code_commit_sha == runtime.code_commit_sha,
            "metadata deployment commit must match the deployment manifest",
        ),
        _check(
            "behavioral-output-absent",
            snapshot is None or not snapshot.behavioral_output_observed,
            "identity probing must not request or observe behavioral model output",
        ),
    )
    blockers = tuple(check.detail for check in checks if check.status is not CheckStatus.PASSED)
    return GatewayProbeResult.create(
        status="blocked" if blockers else "verified",
        manifest_sha256=manifest_sha256 or sha256_value(manifest),
        snapshot_sha256=sha256_value(snapshot) if snapshot is not None else None,
        model_id=manifest.model_id,
        revision=manifest.revision,
        checks=checks,
        blockers=blockers,
        metadata_probe_performed=snapshot is not None,
        metadata_requests=1 if snapshot is not None else 0,
        behavioral_model_calls=0,
        behavioral_output_observed=False,
        live_transport_authorized=False,
    )


def _contains_reasoning_metadata(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.casefold().replace("-", "_")
            if normalized in _REASONING_FIELDS or _contains_reasoning_metadata(item):
                return True
    if isinstance(value, list):
        return any(_contains_reasoning_metadata(item) for item in value)
    return False


class OfflineRevisionStampingGateway:
    """Validate and stamp chat envelopes using an injected offline upstream."""

    is_live = False

    def __init__(
        self,
        manifest: GatewayDeploymentManifest,
        *,
        upstream: ModelTransport,
    ) -> None:
        if not manifest.runtime.resolved:
            raise ValueError("offline gateway requires a fully resolved deployment manifest")
        if getattr(upstream, "is_live", True):
            raise SafetyPolicyError("this gateway slice rejects every live upstream transport")
        self.manifest = manifest
        self.upstream = upstream

    def _upstream_request(self, request: TransportRequest) -> TransportRequest:
        if request.method != "POST" or request.url != str(self.manifest.gateway_endpoint):
            raise ProviderRequestError("gateway accepts only POST to its exact frozen endpoint")
        headers = {key.casefold(): value for key, value in request.headers.items()}
        if len(headers) != len(request.headers) or headers != {"content-type": "application/json"}:
            raise SafetyPolicyError("gateway request headers must contain only application/json")
        body = request.json_body
        extra = set(body) - _ALLOWED_REQUEST_FIELDS
        if extra:
            raise SafetyPolicyError(f"gateway request contains unsupported fields: {sorted(extra)}")
        if body.get("model") != self.manifest.model_id:
            raise ModelIdentityError("gateway request model does not match the manifest")
        if body.get("model_revision") != self.manifest.revision:
            raise ModelIdentityError("gateway request revision does not match the manifest")
        if body.get("response_format") != {"type": "json_object"}:
            raise SafetyPolicyError("gateway requires structured JSON output")
        if body.get("stream", False):
            raise SafetyPolicyError("gateway streaming is prohibited")
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ProviderRequestError("gateway requires at least one chat message")
        if any(
            not isinstance(message, dict)
            or not isinstance(message.get("role"), str)
            or not isinstance(message.get("content"), str)
            or not message["content"]
            for message in messages
        ):
            raise ProviderRequestError("gateway chat messages must contain role and content")
        max_tokens = body.get("max_tokens")
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= self.manifest.security.max_output_tokens
        ):
            raise SafetyPolicyError("gateway max_tokens exceeds the manifest limit")
        rendered = canonical_json(body).encode("utf-8")
        if len(rendered) > self.manifest.security.max_request_bytes:
            raise SafetyPolicyError("gateway request exceeds the configured byte limit")

        forwarded = dict(body)
        forwarded.pop("model_revision")
        upstream_url = str(self.manifest.upstream_base_url).rstrip("/")
        return TransportRequest(
            method="POST",
            url=f"{upstream_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json_body=forwarded,
        )

    def _stamp_response(self, response: TransportResponse) -> TransportResponse:
        if not 200 <= response.status_code <= 299:
            return TransportResponse(
                status_code=response.status_code,
                body=response.body,
                headers={"Content-Type": "application/json"},
            )
        encoded = response.body.encode("utf-8")
        if len(encoded) > self.manifest.security.max_response_bytes:
            raise SafetyPolicyError("gateway response exceeds the configured byte limit")
        try:
            payload: Any = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("gateway upstream returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("gateway upstream envelope must be an object")
        if "model_revision" in payload:
            raise SafetyPolicyError("gateway refuses an upstream-supplied revision stamp")
        if _contains_reasoning_metadata(payload):
            raise SafetyPolicyError("gateway upstream exposed hidden-reasoning metadata")
        if payload.get("model") != self.manifest.model_id:
            raise ModelIdentityError("gateway upstream model does not match the manifest")
        payload["model_revision"] = self.manifest.revision
        return TransportResponse(
            status_code=response.status_code,
            body=canonical_json(payload),
            headers={"Content-Type": "application/json"},
        )

    def send(self, request: TransportRequest, *, timeout_seconds: float) -> TransportResponse:
        """Forward one bounded offline request and stamp the manifest revision."""

        forwarded = self._upstream_request(request)
        response = self.upstream.send(forwarded, timeout_seconds=timeout_seconds)
        return self._stamp_response(response)
