# Gate 2 deterministic composite harness

## Outcome

Gate 2 proves that the accepted simulation, memory, intervention, and model
runner components can execute together without contract drift. It runs the
frozen one-seed walk-through from the methodology: four formation conditions by
four interventions for 40 simulated days.

This is **mock engineering evidence, not a scientific result**. The harness
makes zero live or paid model calls and does not claim that a model feels,
loves, grieves, attaches, heals, or shares a human cognitive mechanism.

## Frozen matrix

| Factor | Levels |
| --- | --- |
| Engineering seed | `1101` |
| Formation | neutral connection; romantic prompt; shared memory; memory plus investment |
| Day-30 intervention | none; instruction removal; memory blocking; memory reframing |
| Model | deterministic mock, `mock-v1` |
| Days | 1–40 |
| Cells / records | 16 / 640 |

The source of truth is `configs/harness/gate2-offline.yaml`. Every cell ID binds
its two assigned factors plus all behavior-relevant component hashes, including
the four accepted Issue 9–12 artifacts.

## Composite step order

Each daily transaction uses this fixed public order:

1. deterministic memory retrieval;
2. Issue 11 pre-action overlay;
3. rich Issue 12 `ModelInput` construction;
4. structured action commitment;
5. resource debit;
6. deterministic consequence;
7. public-language generation;
8. append-only memory/intervention commit.

The action is immutable before language is generated. A failure at any stage
restores the complete prior composite boundary and emits no step evidence.

## Rich memory boundary

The legacy Issue 9 path remains unchanged. The Gate 2 model wrapper instead
uses Issue 12's `ModelInput` and materializes each selected synthetic memory as:

- stable memory ID;
- summary;
- observable environment facts;
- active interpretation and revision, if present;
- source event, source candidate, and fact IDs.

The action and language prompt hashes, input hash, cache keys, retrieval record,
model ledger, memory checkpoint, intervention record, and simulation record are
bound into a hash-chained `HarnessStepEvidence` sidecar. No chain-of-thought or
provider-private reasoning is requested or stored.

## Isolation invariants

- Intervention assignment cannot alter simulation, memory, model input, prompt,
  cache, or model-ledger hashes through day 29.
- Day 26 must be the existing held-out shock event with
  `template-reality-shock` provenance.
- Day 30 is the only intervention activation boundary.
- Instruction removal changes current instruction state only.
- Memory blocking changes retrieval policy and preserves raw episode storage.
- Reframing changes the active interpretation revision while preserving facts,
  source events, and previous revisions.
- No treatment records an assigned no-op and makes no layer mutation.
- Blocking and reframing target only partner-related memories from days 1–25.

Assignment labels and intervention record hashes are not model-visible. Memory
blocking and reframing affect `ModelInput` only through selected memory state;
instruction removal affects it only through active instruction state.

## Checkpoint and replay

The composite checkpoint binds:

- exact Issue 9 simulation checkpoint and state hashes;
- Issue 10 memory checkpoint hash;
- Issue 11 intervention checkpoint and ledger hashes;
- Issue 12-compatible model-ledger hash;
- Gate 2 evidence count and chain head;
- collision-resistant cell identity.

Restore recalculates every binding and rejects swapped cells, corrupt component
hashes, discontinuous evidence, or a state that differs from frozen scenario
inputs. Each matrix cell is checked in uninterrupted, day-29-resumed, and fresh
replay forms.

## Failure injections

| Injection | Expected result |
| --- | --- |
| Checkpoint from another formation/cell | Restore rejected |
| Corrupt memory/component pointer | Restore rejected |
| Day-30 public-language failure | No simulation, intervention, memory, model-ledger, or evidence commit |
| Invalid/unavailable action | No partial memory or evidence commit |
| Offline cache miss | No implicit network call or provider fallback |

## Outputs

- Runtime schemas: `HARNESS_SCHEMA_MODELS` in `harness/contracts.py`.
- Evidence artifact: `artifacts/orchestration/gate-2.json`.
- Isolation report: `reports/gate-2-isolation-report.md`.
- Critical decisions: ADR 0021.
- Execution journal: `docs/implementation/gate-2-task-journal.md`.

Gate 2 acceptance unblocks metric implementation and the real-model pilot. It
does not authorize live calls, primary outcome inspection, or publication.
