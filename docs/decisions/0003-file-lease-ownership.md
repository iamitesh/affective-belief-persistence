# ADR-0003: Explicit file leases for write ownership

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

Specialist agents can work on independent artifacts in parallel, but overlapping
writes can silently corrupt research outputs or overwrite another agent's work.
Directory conventions alone do not provide runtime exclusion or stale-owner
recovery.

## Decision

A task must acquire an explicit lease before writing a managed path. A lease
records its identifier, owner, normalized path scope, acquisition time, expiry,
and status. The supervisor grants, renews, releases, expires, and audits leases.
Overlapping active write scopes are rejected.

## Alternatives considered

- Rely only on documented ownership. This cannot prevent accidental conflicts.
- Use operating-system file locks. They are useful locally but do not capture the
  semantic owner, artifact scope, or portable audit trail needed by the graph.
- Assign one permanent directory per agent. This prevents collaboration on a
  shared artifact and does not handle handoffs cleanly.

## Consequences

- Conflicting tasks wait or fail explicitly instead of overwriting files.
- Stale leases require expiry and recovery rules.
- Path normalization must reject ambiguous traversal and overlapping scopes.
- Lease events become part of the reproducibility and incident audit trail.

## Verification

- [ ] Two active leases cannot cover the same or nested write scope.
- [ ] An expired lease can be recovered deterministically.
- [ ] Completion and failure release all leases owned by the task.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3 artifact ownership](../artifact-ownership.md)
- [PRD: lease contract](../product-requirements-document.md#111-detailed-acceptance-behavior)
