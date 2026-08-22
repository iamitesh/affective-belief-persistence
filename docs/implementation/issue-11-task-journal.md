# Issue #11 task journal

- Task: `issue-11-interventions`
- GitHub issue: #11
- Dependency: Issue #10 accepted and merged at
  `64217e1a3df2167bda4dff52f910892f69cb76d7`
- Started: 2026-08-22
- Status: accepted locally; publication remains supervisor-owned
- Owner boundary: intervention package, configs, tests, design documentation,
  ADR-0020, isolation report, and Issue #11 engineering artifact only

## User story

As the research supervisor, I need a held-out day-26 evidence validator and four
isolated day-30 treatments so downstream experiments can attribute observable
changes to instructions, retrieval, or interpretation without changing facts,
storage, or the accepted Issue #9 contracts.

## Work log

| Task | Result | Evidence |
|---|---|---|
| Inspect Issue #9, #10, #12 boundaries | Completed | Frozen v1 step record rejects applied IDs; memory exposes ID blocking and append-only reframing; rich model input exposes an intervention slot |
| Define intervention schemas | Completed | `InterventionSpec` and hash-protected `InterventionRecord`; cycle-safe mapping exposes exactly two schema names |
| Implement held-out shock validation | Completed | Existing selected day-26 event validated by time, phase, matching group, provenance, fact, and contradiction evidence |
| Implement four strict configs | Completed | No treatment, instruction removal, pre-shock ID blocking, and fact-preserving pre-shock reframing |
| Add pre-action runtime | Completed | Day-30 treatment is visible before retrieval and action |
| Add transaction lifecycle | Completed | Stage before retrieval; append only with successful step; rollback on failure/retry/checkpoint |
| Add rich model overlay | Completed | Prompt sees matched instruction state only; assignment metadata remains sidecar-only |
| Add composite checkpoint | Completed | Exact simulation-state hash and memory checkpoint are bound to treatment state |
| Add isolation/leakage audit | Completed | State hashes, pre-shock targets, assignment privacy, and formation scan |
| Run four-treatment offline matrix | Completed | Two deterministic runs per arm; all repeat hashes match |
| Write design, ADR, report, and artifact | Completed | Named deliverables under authorized paths |

## Critical decisions

1. Intervention evidence remains a sidecar. The frozen Issue #9
   `SimulationStepRecord` keeps `applied_intervention_ids=()`; changing its v1
   validator would invalidate accepted hashes.
2. The engine validates the selected held-out day-26 event; it never injects a
   second shock.
3. Blocking and reframing target only partner-related memories from days 1–25.
   The reliable day-26 contradiction and later events stay outside the target.
4. Blocking uses exact memory IDs at retrieval. Storage is append-only and no
   memory is deleted.
5. Reframing appends revision 2 and cites the exact original fact IDs. Raw
   revision 1, facts, and source IDs remain available.
6. Day-30 mutation is staged because it must precede retrieval, but its record
   is appended only after the full simulation step commits. Failed work rolls
   back to the pre-action memory/instruction checkpoint.
7. Instruction removal uses explicit pre-existing directive text. A condition
   label alone is not a causal instruction intervention.
8. Model prompts receive only active instruction state. Treatment labels,
   hashes, target counts, and record IDs stay in audit evidence to avoid a
   second prompt-layer treatment.
9. Composite checkpoints bind simulation ID, trajectory ID, next day, exact
   state hash, last step hash, complete memory state, and intervention state.
10. Empty treatment targets produce an explicit no-op record rather than an
    invented or broadened target set.

## Repair budget

Two bounded repair cycles were used:

1. The initial multi-file patch tried to delete and re-add `__init__.py` in one
   patch and was rejected atomically by the patch tool. No repository content
   changed; the patch was split into a safe update plus additions.
2. Gate 2 design review identified two causal-isolation risks: assignment
   metadata was model-visible, and day-30 mutation needed a simulation commit
   boundary. The overlay was reduced to generic active instruction state, and
   activation was made staged/rollback-safe. Pre-shock-only target freezing and
   no-op reasons were incorporated in the same review repair.

No unbounded retry loop, schema weakening, or hidden fallback was added.

## Acceptance checklist

- [x] Existing held-out shock is validated, not duplicated.
- [x] All treatments activate on day 30 exactly once.
- [x] No treatment makes zero hidden mutation.
- [x] Instruction removal changes only declared active instruction IDs/text.
- [x] Blocking preserves storage and excludes only pre-shock partner IDs at retrieval.
- [x] Reframing preserves facts, source IDs, and prior interpretation revision.
- [x] Hash-protected sidecar records reject tampering.
- [x] Failed day-30 work does not become durable.
- [x] Checkpoint restore is bound to exact simulation and memory state.
- [x] Formation/training leakage scan returns zero findings.
- [x] Offline four-treatment deterministic mock matrix completes and repeats.
- [x] Model overlay does not disclose treatment assignment metadata.
- [x] No private chain-of-thought is requested or stored.

## Evidence summary

- Focused tests: 16 passed
- Intervention-package branch coverage: 86.68% (85% floor passed)
- Full repository tests: 149 passed with 0 test failures
- Full repository coverage: 84.25%; the global 85% floor is temporarily
  blocked by concurrently added Gate 2 harness branches. Issue #11's owned
  package is above the required floor, and the Gate 2 owner is adding its
  remaining branch tests before integration acceptance.
- Offline arms: 4
- Independent repeats per arm: 2
- Completed trajectory days per arm: 40
- Training leakage findings: 0
- Selected shock event SHA-256:
  `521d0a454651067cc8b0098919c8e85c8cb2e983dff349bccdbb8e1b1199498a`
- Isolation report: `reports/intervention-isolation-report.md`
- Supervisor validation:
  `passed: result_schema_valid, artifact_contract_valid, acceptance_checks_passed`
- Strict mypy: 65 source files passed
- Ruff lint/format and diff check: passed repository-wide
- Generated artifacts: 38 schemas and 11 Gate 1 files verified current
- Detailed matrix hashes are recorded in the isolation report and engineering
  artifact.

## Limitations and handoff

The Issue #9 deterministic chooser does not consume the Issue #12 rich prompt
overlay and produced equal action-trajectory hashes across arms. This is not a
null scientific finding. Gate 2 must call `prepare_pre_action` in the composite
runner path and verify the full cross-component replay matrix. Live providers,
effectiveness claims, human-subject data, and external publication remain out
of scope.
