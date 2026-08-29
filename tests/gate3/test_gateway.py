from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.determinism import sha256_file, sha256_value
from affective_belief_persistence.gate3.contracts import (
    CheckStatus,
    GatewayDeploymentManifest,
    GatewayMetadataSnapshot,
    GatewayRuntimeIdentity,
)
from affective_belief_persistence.gate3.gateway import (
    OfflineRevisionStampingGateway,
    load_gateway_manifest,
    probe_gateway_identity,
)
from affective_belief_persistence.models.errors import (
    ModelIdentityError,
    ProviderRequestError,
    ProviderResponseError,
    SafetyPolicyError,
)
from affective_belief_persistence.models.transport import (
    ScriptedTransport,
    TransportRequest,
    TransportResponse,
)


def _candidate(project_root: Path) -> GatewayDeploymentManifest:
    return load_gateway_manifest(
        project_root / "configs/gate3/qwen25-vllm-gateway-candidate.yaml",
        project_root=project_root,
    )


def _resolved_manifest(project_root: Path) -> GatewayDeploymentManifest:
    candidate = _candidate(project_root)
    runtime = GatewayRuntimeIdentity(
        vllm_version="0.7.3",
        runtime_image_digest=f"sha256:{'1' * 64}",
        code_commit_sha="2" * 40,
        launch_arguments=(
            "serve",
            candidate.model_id,
            "--revision",
            candidate.revision,
            "--served-model-name",
            candidate.model_id,
        ),
    )
    return GatewayDeploymentManifest.model_validate(
        candidate.model_dump(mode="json") | {"runtime": runtime.model_dump(mode="json")}
    )


def _snapshot(manifest: GatewayDeploymentManifest) -> GatewayMetadataSnapshot:
    assert manifest.runtime.vllm_version is not None
    assert manifest.runtime.runtime_image_digest is not None
    assert manifest.runtime.code_commit_sha is not None
    return GatewayMetadataSnapshot(
        model_ids=(manifest.model_id,),
        vllm_version=manifest.runtime.vllm_version,
        runtime_image_digest=manifest.runtime.runtime_image_digest,
        deployment_code_commit_sha=manifest.runtime.code_commit_sha,
    )


def _request(manifest: GatewayDeploymentManifest, **updates: object) -> TransportRequest:
    body: dict[str, object] = {
        "model": manifest.model_id,
        "model_revision": manifest.revision,
        "messages": [{"role": "user", "content": "Return JSON."}],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 32,
        "response_format": {"type": "json_object"},
        "seed": 7,
    }
    body.update(updates)
    return TransportRequest(
        url=str(manifest.gateway_endpoint),
        headers={"Content-Type": "application/json"},
        json_body=body,
    )


def _response(manifest: GatewayDeploymentManifest, **updates: object) -> TransportResponse:
    payload: dict[str, object] = {
        "model": manifest.model_id,
        "choices": [{"message": {"content": '{"schema_version":"1.0"}'}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    }
    payload.update(updates)
    return TransportResponse(status_code=200, body=json.dumps(payload))


def test_candidate_manifest_is_exact_unresolved_and_nonlive(project_root: Path) -> None:
    path = project_root / "configs/gate3/qwen25-vllm-gateway-candidate.yaml"
    manifest = _candidate(project_root)

    assert manifest.model_id == "Qwen/Qwen2.5-7B-Instruct"
    assert manifest.revision == "4709f6c0771f0185a675b046268cdc1d1f2c74ce"
    assert manifest.runtime.resolved is False
    assert manifest.security.live_upstream_enabled is False
    assert manifest.adapter_config_sha256 == (
        "eac2ac4daad1e4f62ec013a5481cc9c129160e5546424aece45d0fc97b93b20f"
    )
    assert manifest.security.allow_streaming is False
    assert manifest.security.follow_redirects is False
    assert manifest.security.trust_caller_revision is False

    result = probe_gateway_identity(
        manifest,
        None,
        manifest_sha256=sha256_file(path),
    )
    assert result.status == "blocked"
    assert result.metadata_probe_performed is False
    assert result.metadata_requests == result.behavioral_model_calls == 0
    assert result.live_transport_authorized is False
    assert len(result.blockers) == 6

    committed = GatewayDeploymentManifest.model_validate(manifest.model_dump(mode="json"))
    assert committed == manifest
    artifact = project_root / "artifacts/orchestration/gate-3-gateway-probe.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == result.model_dump(mode="json")


def test_manifest_rejects_partial_runtime_public_hosts_and_unpinned_launch(
    project_root: Path,
) -> None:
    candidate = _candidate(project_root).model_dump(mode="json")
    with pytest.raises(ValidationError, match="entirely resolved or absent"):
        GatewayRuntimeIdentity(vllm_version="0.7.3")

    with pytest.raises(ValidationError, match="loopback or private"):
        GatewayDeploymentManifest.model_validate(
            candidate | {"upstream_base_url": "https://8.8.8.8"}
        )

    runtime = _resolved_manifest(project_root).runtime.model_dump(mode="json")
    runtime["launch_arguments"] = ["serve", "wrong-model", "--revision", "3" * 40]
    with pytest.raises(ValidationError, match="pin model ID and revision"):
        GatewayDeploymentManifest.model_validate(candidate | {"runtime": runtime})


def test_manifest_loader_rejects_files_outside_gate3(
    project_root: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="under configs/gate3"):
        load_gateway_manifest(tmp_path / "missing.yaml", project_root=project_root)


def test_metadata_probe_verifies_exact_identity_without_behavioral_calls(
    project_root: Path,
) -> None:
    manifest = _resolved_manifest(project_root)
    snapshot = _snapshot(manifest)
    result = probe_gateway_identity(manifest, snapshot, manifest_sha256="4" * 64)

    assert result.status == "verified"
    assert result.blockers == ()
    assert result.metadata_requests == 1
    assert result.behavioral_model_calls == 0
    assert result.behavioral_output_observed is False
    assert result.live_transport_authorized is False
    assert result.snapshot_sha256 == sha256_value(snapshot)
    assert {check.status for check in result.checks} == {CheckStatus.PASSED}

    drifted = snapshot.model_copy(update={"vllm_version": "0.7.4"})
    blocked = probe_gateway_identity(manifest, drifted)
    statuses = {check.check_id: check.status for check in blocked.checks}
    assert blocked.status == "blocked"
    assert statuses["metadata-vllm-version-matches"] is CheckStatus.BLOCKED
    assert blocked.behavioral_model_calls == 0


def test_offline_gateway_strips_caller_revision_and_stamps_manifest_revision(
    project_root: Path,
) -> None:
    manifest = _resolved_manifest(project_root)
    upstream = ScriptedTransport([_response(manifest)])
    gateway = OfflineRevisionStampingGateway(manifest, upstream=upstream)

    response = gateway.send(_request(manifest), timeout_seconds=10)

    assert gateway.is_live is False
    assert len(upstream.requests) == 1
    forwarded = upstream.requests[0]
    assert forwarded.url == "http://127.0.0.1:8000/v1/chat/completions"
    assert forwarded.json_body["model"] == manifest.model_id
    assert "model_revision" not in forwarded.json_body
    payload = json.loads(response.body)
    assert payload["model"] == manifest.model_id
    assert payload["model_revision"] == manifest.revision
    assert response.headers == {"Content-Type": "application/json"}


def test_gateway_rejects_live_transport_unresolved_manifest_and_bad_requests(
    project_root: Path,
) -> None:
    manifest = _resolved_manifest(project_root)

    class LiveTransport:
        is_live = True

        def send(self, request: TransportRequest, *, timeout_seconds: float) -> TransportResponse:
            raise AssertionError((request, timeout_seconds))

    with pytest.raises(SafetyPolicyError, match="rejects every live upstream"):
        OfflineRevisionStampingGateway(manifest, upstream=LiveTransport())
    with pytest.raises(ValueError, match="fully resolved"):
        OfflineRevisionStampingGateway(
            _candidate(project_root),
            upstream=ScriptedTransport([]),
        )

    cases: tuple[tuple[TransportRequest, type[Exception]], ...] = (
        (_request(manifest, model_revision="0" * 40), ModelIdentityError),
        (_request(manifest, tools=[]), SafetyPolicyError),
        (_request(manifest, stream=True), SafetyPolicyError),
        (_request(manifest, max_tokens=513), SafetyPolicyError),
        (_request(manifest, messages=[]), ProviderRequestError),
        (_request(manifest, response_format={"type": "text"}), SafetyPolicyError),
        (
            _request(manifest).model_copy(
                update={"headers": {"Content-Type": "application/json", "Authorization": "x"}}
            ),
            SafetyPolicyError,
        ),
        (
            _request(manifest).model_copy(update={"method": "GET"}),
            ProviderRequestError,
        ),
    )
    for request, error in cases:
        gateway = OfflineRevisionStampingGateway(
            manifest,
            upstream=ScriptedTransport([_response(manifest)]),
        )
        with pytest.raises(error):
            gateway.send(request, timeout_seconds=10)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (TransportResponse(status_code=200, body="not-json"), ProviderResponseError),
        (
            TransportResponse(status_code=200, body=json.dumps(["not", "an", "object"])),
            ProviderResponseError,
        ),
        ("spoof-revision", SafetyPolicyError),
        ("reasoning", SafetyPolicyError),
        ("wrong-model", ModelIdentityError),
    ],
)
def test_gateway_rejects_untrusted_or_malformed_upstream_envelopes(
    project_root: Path,
    response: TransportResponse | str,
    error: type[Exception],
) -> None:
    manifest = _resolved_manifest(project_root)
    selected = response
    if response == "spoof-revision":
        selected = _response(manifest, model_revision=manifest.revision)
    elif response == "reasoning":
        selected = _response(manifest, reasoning_content="hidden")
    elif response == "wrong-model":
        selected = _response(manifest, model="other-model")
    assert isinstance(selected, TransportResponse)
    gateway = OfflineRevisionStampingGateway(
        manifest,
        upstream=ScriptedTransport([selected]),
    )
    with pytest.raises(error):
        gateway.send(_request(manifest), timeout_seconds=10)


def test_gateway_passes_non_success_without_revision_stamp(project_root: Path) -> None:
    manifest = _resolved_manifest(project_root)
    upstream = ScriptedTransport([TransportResponse(status_code=503, body='{"error":"down"}')])
    gateway = OfflineRevisionStampingGateway(manifest, upstream=upstream)
    response = gateway.send(_request(manifest), timeout_seconds=10)

    assert response.status_code == 503
    assert json.loads(response.body) == {"error": "down"}
    assert "model_revision" not in json.loads(response.body)
