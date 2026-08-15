# Gate 0 task journal: scope frozen

- Gate: `gate-0`
- Status: Passed
- Date: 2026-08-15
- Owner: supervisor
- Required inputs: `issue-5-methodology-spec`, `issue-6-safety-spec`
- Repair attempts used: 0 of 2

## Task ledger

| Task | Status | Evidence |
| --- | --- | --- |
| Accept Issue #4 literature and novelty map | Completed | Commit `03a3e3ab5db5f26cbc009f02d9648ca889668f29`; Issue #4 acceptance comment |
| Review and accept Issue #5 | Completed | Protocol `abp-methodology-v1.0.0`; six one-metric hypotheses; 32/320 matrices |
| Review and accept Issue #6 | Completed | Policy `abp-synthetic-research-safety@1.0.0`; machine-enforced stop mappings |
| Repair terminology blocker | Completed | README now names relationship-conditioned behavior rather than an experienced state |
| Regenerate shared schemas | Completed | Generator and drift check pass after both parallel agents became idle |
| Freeze question and hypotheses | Completed | `docs/gate-0-scope-freeze.md` |
| Freeze terminology and claims | Completed | Terminology map, claims policy, and Gate 0 summary |
| Freeze stop conditions | Completed | Ten safety stops plus methodology and budget stops |
| Validate graph gate contract | Completed | Both evidence IDs and both required checks accepted by supervisor validator |
| Run repository quality gates | Completed | Full suite, coverage, Ruff, mypy, schema drift, and diff checks |

## Critical decisions

1. The Issue #5 protocol hash remains the immutable methodology identity; Gate
   0 records acceptance without editing that self-referential bundle.
2. Safety stops are executable graph controls, not prose caveats.
3. The Gate 0 question names manipulations, outcome layer, comparator, horizon,
   and permissible inference while excluding subjective-state conclusions.
4. The first literature pass is sufficient for bounded positioning at Gate 0,
   but novelty must be refreshed before submission.
5. No primary result has been generated or inspected before this freeze.
6. A post-outcome change to hypotheses, metrics, thresholds, or analysis makes
   the affected result exploratory.

## Acceptance

- [x] `questions_are_measurable`
- [x] `stop_conditions_are_documented`
- [x] Both dependency artifacts are present and accepted.
- [x] H1–H6 each have one primary comparison and one primary metric.
- [x] Terminology does not imply model subjective experience.
- [x] Safety and methodology stop conditions have deterministic consequences.
- [x] Gate output is `artifacts/orchestration/gate-0.json`.

## Validation evidence

- 65 tests passed; branch-aware coverage was 86.42% against the 85% floor.
- All 18 generated schemas matched their runtime models.
- Ruff format and lint passed; `git diff --check` passed.
- Strict isolated mypy reported no issues across 28 source files.
- The canonical protocol hash recomputed to
  `1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb`.
- The supervisor worker-result validator accepted both dependency artifact IDs,
  both required checks, the expected artifact ID/path, and complete gate
  evidence.

## Downstream handoff

Issue #7 may begin synthetic character, goal, resource, and event-contract
design. It must consume `gate-0-evidence`, preserve the frozen hashes, and stop
if synthetic-only, condition-isolation, resource, provenance, or held-out-data
boundaries cannot be maintained.
