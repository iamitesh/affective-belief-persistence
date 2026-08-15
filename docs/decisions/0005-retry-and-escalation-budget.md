# ADR-0005: Two-attempt cap and explicit escalation

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2

## Context

Autonomous workers can return invalid results or fail transiently. Infinite or
poorly bounded retries waste time and compute, obscure systematic errors, and can
prevent downstream tasks from reaching a clear terminal state.

## Decision

Allow no more than two automatic implementation attempts in total: the initial
attempt and one retry. Each failed attempt records a structured reason. If the
second attempt fails, the supervisor moves the task to `ESCALATED` through
`BLOCKED`; it prevents a third attempt. This resolves Issue #2's ambiguous use of
“two retries” in favor of its explicit acceptance criterion that the third
attempt must be prevented.

## Alternatives considered

- No retries make transient failures unnecessarily terminal.
- Exponential retry without a hard cap can exceed the 48-hour timebox.
- A global retry pool is flexible but permits a single unstable task to consume
  resources intended for the rest of the workflow.

## Consequences

- A task has at most two automatic attempts.
- Failures become visible, bounded, and attributable.
- Downstream scheduling must recognize blocked dependencies.
- The supervisor needs error classification so non-retryable failures escalate
  immediately rather than consuming the full budget.

## Verification

- [ ] A retryable failing task runs exactly twice before escalation.
- [ ] A third automatic attempt is never scheduled.
- [ ] A non-retryable error escalates after the first attempt.
- [ ] Retry counts survive checkpoint and resume.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [PRD: failure handling](../product-requirements-document.md#25-testing-and-validation-strategy)
