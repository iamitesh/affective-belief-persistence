# ADR-0025: Propose a pinned self-hosted vLLM gateway for Gate 3

- Status: Proposed; not transport-authorized
- Date: 2026-08-25
- Scope: Gate 3 runtime candidate and immutable model-identity boundary

## Context

Gate 3 needs a real preregistered Qwen-family runtime that can preserve the
action-first two-stage contract and prove the exact model revision. The current
workspace has no GPU runtime or model credential. A hosted provider may expose
the requested model name without proving the weight revision.

Official Qwen documentation supports Qwen2.5-7B-Instruct through vLLM's
OpenAI-compatible and structured-JSON interfaces. The repository's adapter,
however, requires a `model_revision` response field that the documented
standard vLLM envelope does not provide.

## Proposed decision

1. Use `Qwen/Qwen2.5-7B-Instruct` at immutable revision
   `4709f6c0771f0185a675b046268cdc1d1f2c74ce` as the Gate 3 model candidate.
2. Self-host it with an exact vLLM image/package and launch manifest rather than
   depend on an opaque third-party model alias.
3. Put a small private gateway between the existing adapter and vLLM. The
   gateway validates the exact request identity and stamps the revision from
   the hash-bound deployment manifest.
4. Keep the candidate adapter, cache, raw retention, and live calls disabled
   until the remaining authorization fields are approved.
5. Implement a metadata-only capability probe before any behavioral request.
6. Do not treat this proposal as approval of compute, credentials, cost,
   transport, or the pilot.

## Consequences

- The deployment can satisfy the existing OpenAI-compatible contract without
  weakening the revision check or silently changing the accepted adapter.
- The gateway and launch manifest become security- and provenance-critical
  inputs and must be source-locked before transport.
- Self-hosted API pricing is zero but total compute cost is not; Gate 3 still
  requires an explicit USD ceiling.
- Direct vLLM, hosted aliases, and the HF/local endpoint remain blocked unless
  they provide equivalent immutable identity evidence.

## Acceptance required

This ADR remains proposed until the research owner approves the runtime path
and the repository contains tested gateway/probe code, a pinned vLLM runtime,
complete budgets, credential reference, time window, and executing commit.

## References

- [Runtime selection analysis](../gate-3-runtime-selection.md)
- [Gate 3 pilot boundary](../gate-3-pilot.md)
- [ADR-0023](0023-explicit-hash-bound-gate-3-authorization.md)
- [ADR-0024](0024-outcome-blind-gate-3-call-cap-amendment.md)
