# Issue #10 task journal: auditable memory and belief subsystem

- Issue: [#10](https://github.com/iamitesh/affective-belief-persistence/issues/10)
- Status: Accepted
- Date: 2026-08-16
- Owner: memory-system implementation
- Required input artifact: `issue-9-simulation-harness`
- Accepted Issue #9 implementation commit: `508c05b61ad7d06a87c6d277d067227798df4195`
- Accepted Issue #9 merge SHA: `a5bf3bdca8c6444dbc556e6b9dd0ca7daf5a868e`
- Pull request: [#22](https://github.com/iamitesh/affective-belief-persistence/pull/22)
- Merge SHA: `64217e1a3df2167bda4dff52f910892f69cb76d7`
- Repair attempts used: 2 of 2

## Task ledger

| Task | Status | Evidence |
| --- | --- | --- |
| Define immutable memory, retrieval, and belief contracts | Completed | `memory/contracts.py`; import-cycle-safe schema map |
| Implement append-only episode storage | Completed | Raw episodes, access events, reframe events |
| Separate facts from interpretations | Completed | Reframe API has no fact write path |
| Implement deterministic relevance and scoring | Completed | Fixed precision, six logged components |
| Log all candidates and selected top-k | Completed | Hash-protected `RetrievalRecord` |
| Implement stable tie-break | Completed | Ascending memory ID after descending score |
| Implement blocking without deletion | Completed | Query-only ID/tag filters |
| Implement relationship beliefs | Completed | Two-sided evidence, confidence bounds, unknown propositions |
| Define deterministic/model-proposed boundary | Completed | `update_belief_evidence`; structured `BeliefProposal` |
| Add checkpoint/restore | Completed | Nested hash-protected runtime/store/belief checkpoints |
| Integrate retrieval before action | Completed | Existing `DecisionRequest.retrieved_memory_ids` and `beliefs` only |
| Integrate memory after consequence | Completed | Non-durable staging then post-validation commit |
| Preserve default Issue #9 hash | Completed | Frozen trajectory regression test |
| Expose Issue #11 hooks | Completed | ID/tag blocking and fact-preserving reframe |
| Document limitations and confounds | Completed | `docs/memory-and-belief-model.md`; ADR-0018 |

## Critical decisions

1. Raw episodes, retrieval accesses, and reframes are separate append-only event
   streams. Current views are derived rather than mutated.
2. Retrieval uses pure ranking and a later idempotent commit so a failed
   simulation step cannot create a false access event.
3. Every score component is bounded and rounded before ranking. Equal totals use
   the memory ID, not a random draw.
4. Blocking changes only the retrieval filter. Reframing changes only a cited
   interpretation and preserves the authoritative fact tuple.
5. Belief evidence IDs are stored-memory IDs and are integrity checked in both
   directions. Confidence is bounded; generic evidence leaves romantic and
   reciprocal propositions unknown.
6. No contract includes rationale, hidden state, or chain-of-thought text.
7. Issue #9 v1 hashed models remain unchanged. Memory uses an optional provider
   and separate checkpoint sidecar.
8. Enabled resume requires a simulation checkpoint and memory sidecar captured
   at the same completed-step boundary.

These decisions are recorded in
[ADR-0018](../decisions/0018-event-sourced-memory-sidecar.md).

## Repair log

1. The first runtime smoke exposed direct Pydantic objects in canonical hash
   payloads. All memory/config/query/interpretation hashes now consume canonical
   JSON model dumps.
2. Integration review found that retrieval access was committed during the
   pre-action lookup. Retrieval was split into pure `rank` and post-step
   `commit`; a failure-after-retrieval regression test now proves no memory,
   retrieval, access, or belief state changes.

No scenario fact, condition, metric threshold, expected direction, or Issue #9
hashed contract changed during repair.

## Validation evidence

| Check | Result |
| --- | --- |
| Focused Issue #10 tests | 14 passed |
| Default no-op trajectory | `fa6c1cbba0a3c5102b69bd4e8aee3feb52330b818ce9fb4519f21aeb95d473ae` |
| Deterministic fixture | Identical ranking, components, top-k, and checkpoint hashes |
| Transaction failure fixture | No durable access, episode, or belief update |
| Integrated resume fixture | Restored memory and simulation equal uninterrupted run |
| Full repository tests | 122 passed |
| Branch-aware coverage | 85.32% against 85% floor |
| Ruff lint and format | Passed |
| Strict mypy | Passed across 56 source files |
| Generated schemas | 32 current, including three memory schemas |
| Gate 1 generated data | 11 files current; frozen dataset hash unchanged |
| Supervisor artifact validation | Passed: `result_schema_valid`, `artifact_contract_valid`, `acceptance_checks_passed` |

## Handoff

Issue #11 may use `MemoryRuntime.set_blocked_memory_ids`,
`set_blocked_condition_tags`, and `EpisodeStore.reframe`. Issue #14 may consume
retrieval records and belief versions as auditable sidecars. Downstream work must
not treat lexical relevance, salience, confidence, or relationship fields as
human subjective state.
