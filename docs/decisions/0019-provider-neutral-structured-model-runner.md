# ADR-0019: Use strict two-stage adapters with injected transports and immutable replay

- Status: Accepted for Issue #12 implementation
- Date: 2026-08-16
- Scope: Issue #12, Gate 2, Gate 3 pilot, and downstream execution

## Context

Issue #9 commits a structured action before it requests public language. Model
integration must preserve that ordering while allowing comparison across model
families. Hosted APIs differ in request envelopes, errors, identity reporting,
structured-output support, and retention terms. A network-backed CI run would
be non-deterministic, require credentials, create cost, and make accepted
replays depend on provider availability.

The frozen v1 `ModelConfig`, `DecisionRequest`, `ModelDecision`, simulation
records, checkpoint format, and pinned mock/scenario inputs are already part of
accepted Issue #9 evidence. Reusing or widening those classes for provider
configuration would change hashed contracts and risk breaking replay.

## Decision

Use a strict runner sidecar contract rather than changing the frozen root model
config. Implement one provider-neutral base adapter with distinct
`select_action` and `generate_public_language` stages. Expose a richer,
cycle-safe `ModelInput` for future memory/intervention integration and bridge
the fields available in Issue #9 without inventing unavailable context.

Implement OpenAI-compatible and local/HF HTTP-family request/response shapes
behind an injected `ModelTransport`. Do not construct a network client in the
research package. CI uses `ScriptedTransport`; a live pilot requires separate
human-approved injection, budget, credentials, and run manifest.

Require every response envelope to echo the exact configured model ID and
revision. Reject missing or mismatched identity. Do not define a fallback
field, and reject undeclared config fields.

Parse exactly one strict JSON object. Verify action membership, exact catalog
cost, and memory/evidence references before returning an Issue #9
`ActionSelection`. Permit one deterministic repair only for malformed JSON or
schema mismatch. Treat an unrepaired output as an invalid run; never synthesize
or substitute an action. Normalize retryable transport failures and cap retries
at the frozen sidecar budget.

Address cached responses by the complete credential-free invocation contract.
Persist raw provider envelopes only after an injected retention policy permits
them. Make cache entries immutable and hash-validated. Reproducible provider
replay reads an accepted cached response and never regenerates it with a live
call.

Version prompts in the repository. Request only JSON, a concise release-safe
evidence summary, and public language. Reject provider envelopes that expose
common hidden-reasoning or reasoning-token fields.

## Consequences

- The simulator retains its accepted action-before-language invariant.
- Model family comparisons share parsing, retry, repair, cache, provenance, and
  error behavior.
- Root schemas can import `MODEL_RUNNER_SCHEMA_MODELS` without a cycle because
  the runner contracts do not import `schemas.py`.
- Provider response identity requirements may exclude APIs that do not reveal
  a pinned revision; this downgrades availability rather than provenance.
- Offline tests establish transport-contract compatibility only. Live
  compatibility and current costs remain unclaimed.
- Cache misses cannot silently become network calls during deterministic replay.
- Full goal/memory/intervention input waits for approved Issue #10/#11 wiring;
  Issue #12 does not mutate frozen v1 records.

## Alternatives considered

- **Return action and public text together.** Rejected because public language
  could influence or retroactively replace the primary behavioral outcome.
- **Extend the frozen root `ModelConfig`.** Rejected because accepted Issue #9
  replay pins that strict shape and mock configuration.
- **Use provider SDKs directly in adapters.** Rejected because SDK-specific
  retries, credentials, and network behavior would enter the deterministic core.
- **Retry until valid JSON.** Rejected because it hides invalid-output rate,
  changes cost by condition, and can manufacture a valid-looking trajectory.
- **Fall back to another model or revision.** Rejected because model identity is
  an experimental factor and substitution invalidates the manifest.
- **Replay by calling the provider again.** Rejected because stochastic service
  state and provider drift cannot reproduce accepted response bytes.
- **Persist every raw response by default.** Rejected because terms, secrets,
  identifiers, or hidden reasoning may make retention unsafe or unauthorized.

## Verification

- [x] Deterministic mock implements the two-stage Issue #9 contract.
- [x] Two non-mock adapter families pass the same offline action/language matrix.
- [x] Invalid action and cost mismatches fail before language generation.
- [x] Malformed output receives exactly one repair attempt.
- [x] Timeout, rate-limit, retry exhaustion, and identity drift are categorized.
- [x] Immutable safe-cache replay makes no transport call.
- [x] Prompt privacy checks reject private-reasoning requests.
- [ ] Human owner approves and runs a budgeted live pilot with pinned revisions.

## References

- [Issue #12](https://github.com/iamitesh/affective-belief-persistence/issues/12)
- [Model runner](../model-runner.md)
- [Compatibility report](../../reports/model-compatibility-report.md)
- [ADR-0017](0017-deterministic-action-first-simulation.md)
- [Safety and claims](../safety-and-claims.md)
