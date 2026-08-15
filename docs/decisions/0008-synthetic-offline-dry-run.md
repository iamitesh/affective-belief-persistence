# ADR-0008: Synthetic and offline first dry run

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

The orchestration layer must be validated independently of model-provider
availability, credentials, personal data, and stochastic generation. A live-model
first test would mix orchestration defects with network and inference variability.

## Decision

The first end-to-end graph uses only synthetic tasks and the deterministic mock
model established by Issue #3. It performs no network calls, reads no private
relationship data, requires no API key, and emits deterministic artifacts for a
fixed seed and configuration.

## Alternatives considered

- Start with a live provider for realism. This makes failures harder to isolate
  and introduces cost and nondeterminism too early.
- Use real personal histories. This violates the research privacy boundary and is
  unnecessary for testing orchestration.
- Mock only individual units. Unit tests alone do not validate checkpoint, lease,
  dependency, retry, and artifact handoffs together.

## Consequences

- CI can execute the complete dry run without secrets or specialized hardware.
- The slice proves orchestration behavior, not the scientific hypothesis.
- Provider adapters can be introduced later without changing the supervisor
  contract.
- Synthetic fixture provenance and fixed seeds become release evidence.

## Verification

- [ ] The dry run succeeds with network access disabled and no API credentials.
- [ ] Two same-seed runs produce identical canonical event and state hashes.
- [ ] The run exercises dependencies, leases, checkpoint/resume, retry handling,
  and optional-stage skipping.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [PRD: MVP scope](../product-requirements-document.md#81-in-scope)
