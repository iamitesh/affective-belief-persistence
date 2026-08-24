# Issue #14 task journal

## Task

- Task ID: `issue-14-metrics`
- GitHub issue: [#14](https://github.com/iamitesh/affective-belief-persistence/issues/14)
- Dependency: Gate 2 accepted and merged at
  `e851160665d9b9e3c34be13a9dc6381f86703226`
- Started: 2026-08-24
- Status: accepted locally; publication pending
- Scope: offline metrics, matrix expansion, execution controls, deterministic
  analysis primitives, schemas, tests, reports, and Gate 3 handoff

## User story

As the evaluation owner, I need the frozen behavioral metrics and a reproducible
multi-seed experiment plan implemented before any live pilot so that later
claims derive from structured, versioned evidence instead of an impressionistic
reading of generated text.

## Work log

| Stage | Status | Evidence |
| --- | --- | --- |
| Re-read frozen metric and analysis contracts | Completed | `abp-metrics-v1`, six confirmatory hypotheses, trajectory-first inference |
| Confirm Gate 2 handoff | Completed | Accepted 16-cell/640-step offline harness; live calls remain unauthorized |
| Metric contracts and registry | Completed | Strict metric/result schemas and explicit missingness |
| Component, persistence, and H1–H6 metrics | Completed | Production helpers with known-answer fixtures |
| Pilot/primary matrix expansion | Completed | 32/320 collision-resistant assignments |
| Resumable budget-aware execution | Completed | Immutable result pointers, visible failures, and hard stops |
| Statistical analysis utilities | Completed | Paired blocks, bootstrap, sign flips, effect size, Holm, recovery |
| Documentation and evidence | Completed | ADR-0022, design, non-execution reports, journal, accepted artifact |

## Critical decisions

1. Issue #14 implements measurement infrastructure, not research outcomes.
2. A zero denominator or missing required field yields an explicit missing
   reason, never a numeric zero.
3. Language and action are classified independently before contradiction is
   calculated.
4. The accepted harness does not expose frozen prospective `Q`; normalized
   opportunity cost fails closed unless a future authorized scenario supplies
   those values explicitly.
5. Repeated days are summarized within trajectories before model/seed paired
   contrasts.
6. Run identity binds every behavior-relevant assignment and config hash;
   resume cannot duplicate or overwrite completed raw evidence.
7. Deterministic mock and synthetic fixtures are labeled engineering evidence,
   not findings for either preregistered model family.
8. Live providers, costs, primary execution, and external publication remain
   blocked pending Gate 3 authorization.

## Repair budget

Issue #14 permits at most two bounded implementation repair cycles before any
full batch. Repairs may fix contract or arithmetic defects but may not change a
frozen metric, threshold, hypothesis, expected direction, or exclusion rule.

## Acceptance checklist

- [x] Every frozen component and persistence metric has known-answer tests.
- [x] H1–H6 helpers implement the preregistered block formulas.
- [x] Action/language, fact/interpretation, and raw/derived boundaries are typed.
- [x] Missing, invalid, repaired, and censored observations remain visible.
- [x] Pilot and primary designs expand to 32 and 320 unique assignments.
- [x] Resume is idempotent and completed raw outputs are immutable.
- [x] Budget stops fail closed without creating a completed result.
- [x] Analysis respects trajectory clustering and paired blocks.
- [x] Null, undefined, contradictory, and incomplete summaries are preserved.
- [x] Schemas, config, ADR, reports, artifact, and journal are committed.
- [x] Repository-wide test coverage remains at least 85%.
- [x] Live calls, paid calls, primary outcomes, and scientific claims remain zero.

## Verification evidence

- Evaluation slice: 62 tests passed at 90.70% branch-aware package coverage.
- Repository: 239 tests passed at 87.17% branch-aware coverage.
- Static checks: Ruff, formatting, strict MyPy across 73 source files, generated
  schemas, Gate 1 data verification, and diff hygiene passed.
- Registered schemas: 43 current generated contracts.
- Evaluation config SHA-256:
  `cd68dcfbc07b44ec106dc89efb15bb5f076c684db68b0322b0db2935a8175ac5`.
- Pilot matrix: 32 assignments,
  `8c1393598603473768d1d0ebafed887ea52a11e75c28de74f12dfe45b1cb5459`.
- Primary matrix: 320 assignments,
  `0461144fe4a01147d6f2230d9a3b6b1c24cb77613cc79ca62879ac9a7ef09927`.
- Gate 2 input SHA-256:
  `68b6d265d57bbd390ee70037f623a508896d72515ec56417b591662251746a0f`.
- Gate 1 dataset SHA-256 remains
  `5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387`.

## Gate 3 handoff

Gate 3 may begin only after this checklist passes and the supervisor separately
records exact model revisions, access, prompt/dataset/metric hashes, and hard
call, token, cost, and wall-clock limits. Until then, pilot and primary result
reports remain explicit non-execution records.
