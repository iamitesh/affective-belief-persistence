# ADR-0004: Typed JSON events and checkpoints

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

Issue #2 must support interruption recovery, auditability, and deterministic
replay. Pickle or opaque framework snapshots are unsafe, difficult to inspect,
and tightly coupled to a specific runtime implementation.

## Decision

Represent task state, result envelopes, leases, budgets, events, and checkpoints
with typed application models. Persist them as versioned, canonical JSON. Events
form an append-only history; checkpoints are validated snapshots that reference
the last applied event and include integrity metadata.

## Alternatives considered

- In-memory-only state cannot resume after interruption.
- Pickle is convenient but unsafe for untrusted inputs and unstable across code
  changes.
- A database is appropriate at larger scale but adds operational scope that the
  offline MVP does not require.

## Consequences

- Humans and tools can inspect the orchestration trail without custom decoding.
- Schema versions and migrations must be managed deliberately.
- Canonical serialization is required for meaningful hashes.
- Checkpoint writes must be atomic to avoid partial-state recovery.

## Verification

- [ ] Every persisted event and checkpoint validates against its typed model.
- [ ] Resume continues after the last applied event without redoing completed work.
- [ ] Invalid or truncated checkpoint data fails safely with a clear error.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [PRD: persistent workflow state](../product-requirements-document.md#11-functional-requirements)
