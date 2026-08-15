# ADR-0001: Supervisor-owned deterministic workflow state

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

Specialist agents may finish concurrently, fail, time out, or return results in a
different order between runs. If workers mutate shared workflow state directly,
the result depends on scheduling and becomes difficult to replay or audit.

## Decision

The supervisor is the only component allowed to transition authoritative task,
budget, lease, gate, and workflow state. Workers receive immutable task inputs
and return proposed results. The supervisor validates and applies those results
in a stable order using deterministic transition rules.

## Alternatives considered

- Let every worker update shared state directly. This is simpler initially but
  introduces races and non-reproducible transitions.
- Use distributed consensus. It is unnecessary for the single-process,
  48-hour MVP and would consume the sprint on infrastructure.

## Consequences

- Replays can reproduce state transitions from the same inputs and events.
- Workers remain easier to test because they do not own global state.
- The supervisor becomes a critical component and must validate every result.
- Parallel work can complete out of order, but authoritative application may be
  serialized to preserve determinism.

## Verification

- [ ] Reordering worker completion does not change the final state hash.
- [ ] Direct worker mutation of supervisor state is rejected by the interface.
- [ ] Every state transition records its triggering event.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [PRD: supervisor](../product-requirements-document.md#101-supervisor)
