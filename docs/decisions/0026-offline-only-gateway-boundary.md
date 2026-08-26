# ADR-0026: Keep the first revision-stamping gateway boundary offline-only

- Status: Accepted for Gate 3 offline implementation
- Date: 2026-08-26
- Scope: revision-stamping logic and metadata-probe evidence before transport

## Context

ADR-0025 proposes a private gateway because the standard vLLM response does
not prove the loaded immutable weight revision. The repository still lacks an
approved compute host, vLLM version/image digest, credential reference,
token/cost/runtime budgets, authorization window, and executing commit.

Implementing an HTTP client or server now would create a transport path before
those facts exist. Deferring all code would leave the identity boundary
untested.

## Decision

1. Implement request filtering, upstream-envelope validation, and revision
   stamping as a pure injected transport boundary.
2. Reject every upstream whose `is_live` property is true.
3. Strip the caller's `model_revision` before forwarding and stamp the response
   only from a fully resolved deployment manifest.
4. Bind the manifest to the exact disabled adapter bytes and private IP-literal
   endpoints.
5. Reject extra request fields, streaming, credentials in inbound headers,
   oversized bodies, model drift, upstream revision stamps, and hidden-reasoning
   metadata.
6. Represent runtime identity probing as a hash-bound comparison against an
   injected metadata-only snapshot with exactly zero behavioral model calls.
7. Commit the unresolved real candidate as blocked evidence; do not invent a
   vLLM version, image digest, launch command, runtime snapshot, or code commit.

## Consequences

- CI can test the complete envelope and provenance behavior without network,
  credentials, model weights, or GPU access.
- The repository has no newly callable live-model path.
- A future live gateway/server is a separate reviewed implementation and must
  consume a resolved manifest plus complete Gate 3 authorization.
- A verified metadata probe proves only that supplied runtime metadata matches
  the manifest. It is not behavioral evidence and cannot pass Gate 3.

## Evidence

- `src/affective_belief_persistence/gate3/gateway.py`
- `configs/gate3/qwen25-vllm-gateway-candidate.yaml`
- `artifacts/orchestration/gate-3-gateway-probe.json`
- `tests/gate3/test_gateway.py`
- `scripts/gate3_gateway_probe.py`
