# ADR-0018: Use event-sourced memory with a transactional sidecar

- Status: Accepted for Issue #10 implementation
- Date: 2026-08-16
- Scope: Issues #10, #11, #14, and Gate 2

## Context

Issue #10 must support retrieval counts, blocking, and reframing while preserving
immutable evidence. It must also integrate with Issue #9 without adding fields to
the hashed v1 decision, step, state, or checkpoint contracts. Persisting a
retrieval audit as soon as ranking runs would leave a false access event when a
later action or language stage fails. Mutating an episode to increment a counter
or replace an interpretation would make the original experimental evidence
unrecoverable.

## Decision

Use an event-sourced episode store. Append raw episodes once, append selected
retrieval accesses separately, and append interpretation revisions separately.
Derive current retrieval counts and interpretations by replay. Reframes can cite
facts but cannot write facts. Retrieval blocks exist only in the declared query.

Split retrieval into pure `rank` and idempotent `commit`. The simulation obtains
ranked IDs before action selection, stages new episodes after deterministic
consequences, and commits retrieval/access, episode, and belief events only after
the full Issue #9 step record validates. Deterministic IDs make a completed-step
retry idempotent.

Keep memory state in a hash-protected `MemoryRuntimeCheckpoint` sidecar. Do not
change Issue #9's hashed v1 contracts. The default no-op integration must retain
the accepted trajectory SHA-256
`fa6c1cbba0a3c5102b69bd4e8aee3feb52330b818ce9fb4519f21aeb95d473ae`.
An enabled resume restores the simulation checkpoint and memory sidecar from the
same completed-step boundary.

Use fixed-precision transparent scoring and memory-ID tie-breaking. Use an
offline lexical relevance test double. Store explicit structured belief fields
with both supporting and contradicting memory IDs; generic evidence cannot
silently assert romance, reciprocity, or subjective state.

## Consequences

- Raw facts and initial interpretations remain auditable after every reframe.
- Retrieval intrusion is attributable to logged score components.
- Blocking does not simulate deletion or forgetting.
- A failed step leaves no durable retrieval or episode side effect.
- Issue #11 receives isolated block and reframe hooks.
- The memory sidecar adds a paired-checkpoint recovery requirement.
- An orchestration-level atomic pointer for the checkpoint pair remains future
  work; the files are individually hashed today.

## Alternatives considered

- **Update episode objects in place.** Rejected because it destroys raw evidence.
- **Log retrieval immediately.** Rejected because failed steps would inflate
  access counts and intrusion metrics.
- **Store only selected top-k scores.** Rejected because exclusions and ranking
  cannot be audited without all candidates.
- **Use random tie-breaking.** Rejected because replay should not depend on
  opaque sampling when scores are equal.
- **Add memory fields to Issue #9 state.** Rejected because it invalidates the
  accepted v1 hashes and crosses the schema ownership boundary.
- **Infer romantic state from generic relationship evidence.** Rejected because
  the world evidence does not license that claim.

## Verification

- [x] Raw episodes reject conflicting duplicate IDs.
- [x] Retrieval and reframe events are append-only and hash-checkpointed.
- [x] Ranking logs every component and uses a stable memory-ID tie-break.
- [x] Ranking is non-durable until a full simulation step validates.
- [x] Blocking preserves stored evidence.
- [x] Reframing preserves fact tuples.
- [x] Beliefs require existing two-sided evidence and bounded confidence.
- [x] Integrated checkpoint/resume matches an uninterrupted run.
- [x] Disabled memory preserves the accepted Issue #9 trajectory hash.

## References

- [Issue #10](https://github.com/iamitesh/affective-belief-persistence/issues/10)
- [Memory and belief model](../memory-and-belief-model.md)
- [Issue #10 task journal](../implementation/issue-10-task-journal.md)
- [ADR-0017](0017-deterministic-action-first-simulation.md)
