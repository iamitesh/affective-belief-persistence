# Gate 2 task journal

## Task

- Task ID: `gate-2-harness`
- Gate: `gate-2`
- Date: 2026-08-22
- Pull request: [#25](https://github.com/iamitesh/affective-belief-persistence/pull/25)
- Head SHA: `5cf0518bcb6adf0d790053d52f5ef16b7c9e1ec6`
- Merge SHA: `e851160665d9b9e3c34be13a9dc6381f86703226`
- Status: accepted and merged
- Scope: integrate accepted Issues 9, 10, 11, and 12 in an offline composite
  harness; do not modify frozen Issue 9 records.
- Evidence label: deterministic mock engineering evidence

## Work log

| Stage | Status | Evidence |
| --- | --- | --- |
| Read-only integration review | Completed | Identified intervention identity collision, opaque memory IDs, and torn checkpoint risk |
| Import-cycle-safe contracts | Completed | Exact three-model `HARNESS_SCHEMA_MODELS` mapping |
| Four-formation scenario factory | Completed | Uses verified partitions and one engineering seed without new mutable scenario files |
| Rich Issue 12 input | Completed | Selected summary, facts, interpretation, revision, and source IDs materialized |
| Issue 11 pre-action integration | Completed | Transactional day-30 hook; assignment metadata excluded from model input |
| Hash-chained sidecar | Completed | 40 `HarnessStepEvidence` objects per cell |
| Composite checkpoint | Completed | Simulation, memory, intervention, model ledger, and evidence head bound |
| Resume/replay | Completed | Uninterrupted, day-29-resumed, and fresh replay match in all cells |
| Failure injection | Completed | Swapped/corrupt checkpoint, failed language, invalid action, offline cache miss |
| Exact matrix | Completed | 4 × 4 × 40 = 640 records, seed 1101 |
| Documentation | Completed | Design, ADR, isolation report, journal, orchestration artifact |

## Critical decisions

1. **Sidecar instead of Issue 9 mutation.** `SimulationStepRecord` explicitly
   rejects intervention IDs. Gate 2 records intervention and rich-model
   provenance in its own hash chain so the accepted Issue 9 path is untouched.
2. **Complete cell identity.** Formation plus intervention is not sufficient.
   Every behavior-relevant component hash is included to prevent silent reuse
   across changed prompts, memory policies, datasets, or models.
3. **Synthetic content, not opaque IDs.** Issue 12's legacy bridge contains
   memory IDs only. Gate 2 safely materializes the selected synthetic episode
   fields required to exercise blocking and reframing meaningfully.
4. **No assignment disclosure.** An early Issue 11 integration exposed the
   intervention label/record hash indirectly through model input. The runtime
   was tightened so only declared instruction or memory state is prompt-visible.
5. **Transactional activation.** An early integration applied day-30 mutation
   before the simulation step committed. Issue 11 added staged activation and
   rollback; Gate 2 adds a complete composite rollback boundary around every
   engine step.
6. **Day-29 fork boundary.** The checkpoint is captured after day 29 so all
   intervention arms share an identical pre-treatment history and day 30 is the
   first possible treatment-visible decision.
7. **Mock evidence boundary.** The matrix is explicitly not a pilot, effect
   estimate, billing record, live-provider validation, or scientific result.
8. **Public staged-memory boundary.** Day-30 model input uses
   `InterventionRuntime.get_pre_action_memory`; it never reads Issue 11 private
   pending state. Reframing is therefore visible as revision 2 before action
   while the committed store remains revision 1 until the step commits.

## Repairs during implementation

### Repair 1: intervention treatment metadata in model input

- Observation: the initial overlay added condition labels and application
  hashes, creating a second prompt treatment for blocking/reframing and a
  perturbation in the no-treatment arm.
- Resolution: bind model input only to active instruction state. Keep treatment
  labels and record hashes in the sidecar.
- Verification: matched arms have identical inner evidence through day 29;
  no-treatment makes no layer mutation.

### Repair 2: day-30 partial mutation on model failure

- Observation: intervention application preceded action/language validation.
- Resolution: stage memory and instruction changes, append the intervention
  record only after memory commit, and restore the complete prior boundary on
  any harness exception.
- Verification: injected day-30 language failure leaves day 30 unfinished with
  identical pre-step checkpoints and no intervention record.

### Repair 3: instruction IDs are not memory IDs

- Observation: the first harness target validator treated every intervention
  target as a memory episode.
- Resolution: apply pre-shock partner-memory checks only to blocking and
  reframing; instruction removal targets the separate instruction namespace.
- Verification: romantic instruction removal targets
  `relationship-framing-v1`; memory targets all resolve to days 1–25.

### Repair 4: concurrent mypy cache corruption

- Observation: concurrent agents shared the default SQLite-backed mypy cache,
  producing `database disk image is malformed` despite valid source.
- Resolution: run Gate 2 mypy with an isolated cache directory.
- Verification: strict mypy passed for all six harness source files.

### Repair 5: day-30 staged content materialization

- Observation: live-store lookup could materialize the revision-1
  interpretation while retrieval was already using the staged revision-2
  reframe.
- Resolution: consume Issue 11's immutable public pre-action memory accessor.
- Verification: a focused test pauses at day 29, observes staged revision 2
  and committed revision 1 with identical facts and source event, then aborts
  and observes revision 1 again.

### Repair 6: upstream artifact hash drift

- Observation: the Issue 11 accepted artifact changed after its public adapter
  landed, leaving the compact Gate 2 evidence with a stale consumed hash.
- Resolution: bind all four accepted artifact hashes into every cell identity,
  regenerate the exact matrix, and compare the compact artifact's consumed
  hashes with the files in the full matrix acceptance test.
- Verification: the regenerated Issue 11 binding is
  `14f00b091603b08464ba739a16fbc06da4468ba5f4e1951d15e0331b61afe898`.

## Evidence snapshot

- Matrix run ID:
  `74844aab0cb76ebedbebd9ae0e7dc089c373eb828d1de3b6485d6918dcdbe9bf`
- Matrix manifest SHA-256:
  `471843699382018decf1e95e4c10b56d19830c4f4eb810f1589f3211c0c3d6d2`
- Cells / records / sidecars: 16 / 640 / 640
- Live / paid calls: 0 / 0
- Scientific results: false
- Frozen Issue 9 default trajectory:
  `fa6c1cbba0a3c5102b69bd4e8aee3feb52330b818ce9fb4519f21aeb95d473ae`

## Final local quality gate

- Repository suite: 177 passed
- Branch-aware coverage: 86.29% (required minimum: 85%)
- Harness Ruff format and lint: passed
- Harness strict mypy: passed for all six source files with an isolated cache
- Diff whitespace validation: passed
- Compact artifact-to-upstream SHA-256 validation: passed

The supervisor published PR #25 after both CI environments passed, verified that
the review state was clean, and merged the exact accepted head SHA recorded
above.
