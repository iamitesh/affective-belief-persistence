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

## Research Gate 0 decisions

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-0010](0010-measurable-non-anthropomorphic-novelty.md) | Position novelty as a measurable experimental combination | Accepted |
| [ADR-0011](0011-preregistered-action-first-methodology.md) | Freeze an action-first, factorial methodology before outcomes exist | Accepted |
| [ADR-0012](0012-machine-enforced-safety-and-claim-boundaries.md) | Enforce safety and claim boundaries as machine-readable graph controls | Accepted |
| [ADR-0013](0013-gate-0-freeze-and-change-control.md) | Freeze Gate 0 inputs under outcome-blind change control | Accepted |

## Data Gate 1 decisions

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-0014](0014-versioned-synthetic-world-contracts.md) | Make strict runtime contracts the source of truth for the synthetic world | Accepted |
| [ADR-0015](0015-deterministic-matched-dataset.md) | Generate matched partitions deterministically and protect held-out content | Accepted |
| [ADR-0016](0016-gate-1-data-freeze.md) | Freeze dataset hashes only after schema, matching, leakage, and provenance checks | Accepted |

## Harness Gate 2 decisions

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-0017](0017-deterministic-action-first-simulation.md) | Use an idempotent two-stage action-first simulation transaction | Accepted for Issue #9 implementation |
| [ADR-0018](0018-event-sourced-memory-sidecar.md) | Keep memory, retrieval, and belief state in an auditable event-sourced sidecar | Accepted for Issue #10 implementation |
| [ADR-0019](0019-provider-neutral-structured-model-runner.md) | Use exact, two-stage provider adapters with immutable validated cache replay | Accepted for Issue #12 implementation |
| [ADR-0020](0020-hash-chained-layer-isolated-interventions.md) | Keep interventions hash-chained, layer-isolated, and transaction-bound | Accepted for Issue #11 implementation |
| [ADR-0021](0021-composite-hash-chained-gate-2-harness.md) | Bind frozen component records through a composite hash-chained Gate 2 sidecar | Accepted for Gate 2 |

## Evaluation Gate 3 decisions

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-0022](0022-versioned-missingness-explicit-evaluation.md) | Keep evaluation versioned, trajectory-first, and missingness-explicit | Accepted for Issue #14 offline implementation |
| [ADR-0023](0023-explicit-hash-bound-gate-3-authorization.md) | Require explicit, hash-bound authorization before Gate 3 transport | Accepted for Gate 3 preflight |

## Related sources

- [Issue #2: supervisor, specialist agents, and shared-state contracts](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3: repository foundation](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [Product Requirements Document](../product-requirements-document.md)
- [Issue #2 task journal](../implementation/issue-2-task-journal.md)
- [Issue #4 task journal](../implementation/issue-4-task-journal.md)
- [Issue #5 task journal](../implementation/issue-5-task-journal.md)
- [Issue #6 task journal](../implementation/issue-6-task-journal.md)
- [Gate 0 task journal](../implementation/gate-0-task-journal.md)
- [Issue #7 task journal](../implementation/issue-7-task-journal.md)
- [Issue #8 task journal](../implementation/issue-8-task-journal.md)
- [Gate 1 task journal](../implementation/gate-1-task-journal.md)
- [Issue #9 task journal](../implementation/issue-9-task-journal.md)
- [Issue #10 task journal](../implementation/issue-10-task-journal.md)
- [Issue #12 task journal](../implementation/issue-12-task-journal.md)
- [Issue #11 task journal](../implementation/issue-11-task-journal.md)
- [Gate 2 task journal](../implementation/gate-2-task-journal.md)
- [Issue #14 task journal](../implementation/issue-14-task-journal.md)
- [Gate 3 task journal](../implementation/gate-3-task-journal.md)
