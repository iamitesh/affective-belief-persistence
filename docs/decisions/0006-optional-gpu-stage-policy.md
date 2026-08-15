# ADR-0006: Optional and skippable GPU training stage

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

The mandatory contribution is the behavioral harness and controlled evaluation.
GPU-backed adapter training is conditional, may be unavailable, and must not
block a valid offline MVP or the release of baseline experimental evidence.

## Decision

Represent GPU training as an optional workflow task. If its capability or budget
precondition is not satisfied, the supervisor records `CANCELLED` with a typed
no-artifact skip reason and schedules the non-training baseline path. `CANCELLED`
is used because it is part of Issue #2's approved state vocabulary; for an
optional task it is a planned skip, not a failure, and must not block mandatory
downstream evaluation and reporting tasks.

## Alternatives considered

- Make training mandatory, which makes external compute availability a release
  dependency.
- Remove training from the graph, which loses a useful future comparison branch.
- Treat missing GPU capacity as failure, which misrepresents a planned fallback.

## Consequences

- The MVP remains runnable on CPU-only and offline environments.
- Reports must distinguish baseline and adapted-model evidence.
- Tasks depending specifically on the trained adapter also skip; tasks depending
  on the broader model stage may follow the baseline branch.
- Capability checks and skip reasons must be machine-readable.

## Verification

- [ ] A CPU-only dry run completes with the optional training task marked
  `CANCELLED` and a structured skip reason.
- [ ] Mandatory downstream tasks still become ready on the baseline branch.
- [ ] A configured GPU capability enables the optional branch without changing
  unrelated scheduling behavior.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [PRD: optional adapter](../product-requirements-document.md#11-functional-requirements)
