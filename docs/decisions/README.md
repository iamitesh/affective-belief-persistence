# Architecture Decision Records

This directory records consequential design decisions for the Affective Belief
Persistence research platform. Decision records are append-only: if a decision
changes, add a new ADR that supersedes the old one instead of rewriting history.

## Issue #2 decisions

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-0001](0001-supervisor-owned-deterministic-state.md) | Keep workflow state deterministic and supervisor-owned | Accepted |
| [ADR-0002](0002-bounded-worker-concurrency.md) | Limit execution to three workers and apply results through the supervisor | Accepted |
| [ADR-0003](0003-file-lease-ownership.md) | Require explicit file leases for write ownership | Accepted |
| [ADR-0004](0004-typed-json-events-checkpoints.md) | Persist typed JSON events and checkpoints | Accepted |
| [ADR-0005](0005-retry-and-escalation-budget.md) | Prevent a third automatic task attempt | Accepted |
| [ADR-0006](0006-optional-gpu-stage-policy.md) | Treat GPU training as optional and skippable | Accepted |
| [ADR-0007](0007-connector-first-publication.md) | Publish through the GitHub connector while local Git is unsynchronized | Accepted |
| [ADR-0008](0008-synthetic-offline-dry-run.md) | Make the first vertical slice synthetic and offline | Accepted |
| [ADR-0009](0009-agent-registry-layout.md) | Keep the registry inside the foundation's agent-config directory | Accepted |

## Related sources

- [Issue #2: supervisor, specialist agents, and shared-state contracts](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3: repository foundation](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [Product Requirements Document](../product-requirements-document.md)
- [Issue #2 task journal](../implementation/issue-2-task-journal.md)
