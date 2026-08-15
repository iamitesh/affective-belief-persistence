# ADR-0002: Three-worker concurrency with supervisor-applied results

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

The research workflow benefits from parallel specialist work, but unconstrained
fan-out increases resource use, file conflicts, nondeterministic behavior, and
failure-recovery complexity. The approved plan sets a maximum of three workers.

## Decision

Run at most three worker threads concurrently. The supervisor schedules only
dependency-ready tasks with valid leases and available budgets. Worker threads
return result envelopes; they never commit global workflow transitions. The
supervisor validates and applies completed envelopes in a stable task-key order.

## Alternatives considered

- Sequential execution is highly reproducible but underuses independent work.
- Unbounded asynchronous tasks maximize throughput but weaken cost control and
  make race conditions more likely.
- Process-based execution provides isolation but is unnecessary for the first
  offline orchestration slice.

## Consequences

- The maximum active worker count is predictable and testable.
- The scheduler needs a ready queue and dependency-aware admission control.
- Long tasks can occupy capacity; timeout and escalation behavior must therefore
  be explicit.
- The limit may later become configurable, but three is the enforced MVP cap.

## Verification

- [ ] A test workload never observes more than three active workers.
- [ ] A fourth ready task waits until a slot is released.
- [ ] Different completion timing produces the same supervisor-owned final state.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [PRD: bounded concurrency](../product-requirements-document.md#11-functional-requirements)
