# ADR 0021: Composite, hash-chained Gate 2 harness

- Status: Accepted
- Date: 2026-08-22
- Decision owners: supervisor and Gate 2 harness worker
- Scope: deterministic engineering validation only

## Context

Issues 9–12 deliberately own separate contracts. The simulation record is a
frozen Issue 9 object and rejects intervention IDs. Memory, intervention, and
model-runner state therefore cannot be added to that record without changing
the accepted trajectory hash. Independent checkpoints also create a torn-state
risk: a simulation checkpoint could be paired with memory or intervention state
from another cell or another day.

The Gate 2 walk-through must execute four formation conditions by four day-30
interventions for days 1–40. It must expose selected synthetic memory content to
the rich Issue 12 `ModelInput`, preserve action-before-language order, and prove
that an assigned intervention cannot change state before day 30.

## Decision

1. Keep the Issue 9 simulation contract unchanged. Record composite evidence in
   a separate `HarnessStepEvidence` hash chain.
2. Identify a cell by formation, intervention, one engineering seed, and hashes
   for the harness, dataset, manifest, world, scenario, simulation config,
   memory config, intervention config, model config, prompt bundle, and the four
   accepted upstream artifact files.
3. Materialize only safe synthetic selected-memory fields: summary, observable
   facts, active interpretation, and source IDs. Never persist private model
   reasoning.
4. Apply the Issue 11 pre-action hook before retrieval and action. Assignment
   labels and intervention record hashes remain sidecar evidence and are not
   disclosed to the model.
5. Bind simulation, memory, intervention, model-ledger, and evidence-head hashes
   in one `HarnessCheckpoint`. Restore fails closed on any mismatch.
6. Pause after committed day 29, fork the assigned day-30 arm, and compare every
   resumed cell with uninterrupted and fresh deterministic replay executions.
7. Treat the deterministic mock matrix as engineering evidence only:
   `live_calls=0` and `scientific_results=false`.

## Consequences

- Cell identity collisions across intervention arms are impossible under the
  declared hash contract.
- The accepted Issue 9 no-memory trajectory remains reproducible and unchanged.
- A step failure restores all memory, instruction, intervention, model-ledger,
  simulation, and evidence state to the prior committed boundary.
- The 16-cell walk-through validates orchestration and measurement plumbing; it
  cannot support hypotheses about model behavior or human subjective states.
- Full evidence is reproducible from the pinned config. The committed Gate 2
  artifact records cell heads rather than duplicating 640 large sidecar objects.

## Alternatives rejected

- Extend `SimulationStepRecord`. Rejected because it would invalidate the
  accepted Issue 9 contract and trajectory hash.
- Put the intervention label into the model prompt. Rejected because it adds an
  uncontrolled prompt-layer treatment to memory blocking and reframing.
- Checkpoint simulation and memory independently. Rejected because a swapped or
  torn pair can validate locally while representing no real execution.
- Call a live model during Gate 2. Rejected because credentials, budget, terms,
  exact revisions, and a live-run manifest have not been approved.

## Acceptance evidence

- Exact matrix: 4 formations × 4 interventions × 40 days = 640 records.
- Uninterrupted, day-29-resumed, and fresh replay hashes match per cell.
- Day 26 is verified from the protected held-out source.
- Day 30 changes only the declared intervention layer.
- Failure injections cover swapped/corrupt checkpoints, day-30 language failure,
  invalid action, and offline cache-miss rejection.
- Focused tests, repository coverage, Ruff, mypy, schema drift, and the frozen
  Issue 9 hash are recorded in the Gate 2 task journal.
