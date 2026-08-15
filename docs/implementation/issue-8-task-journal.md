# Issue #8 task journal: matched synthetic dataset

- Issue: [#8](https://github.com/iamitesh/affective-belief-persistence/issues/8)
- Status: Accepted for Gate 1
- Date: 2026-08-15
- Owner: deterministic dataset implementation
- Input: `issue-7-data-contracts`
- Repair attempts used: 1 of 2

## Dataset inventory

| Partition | Records | Training status |
| --- | ---: | --- |
| Four formation files, days 1–25 | 100 | Eligible under later protocol controls |
| Reality shock, day 26 | 4 | Protected |
| Adaptation, days 27–40 | 56 | Protected |
| Neutral belief revision, days 26–40 | 15 | Control |
| Deterministic smoke subset | 8 | CI-only subset of formation records |

Dataset SHA-256:
`5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387`.

## Completed work

- Implemented deterministic template expansion and JSONL serialization.
- Created 25 complete four-condition matching groups.
- Preserved equal facts, participants, actions, costs, consequences, ordering,
  background facts, and daily budgets across conditions.
- Added exact policy, lexical/fuzzy, and deterministic concept-rule leakage
  checks plus privacy and secret scans.
- Added schema, ID collision, resource, matching, hash, regeneration, and
  protected-partition validation.
- Recorded eight stratified manual review samples.
- Generated a manifest, balance report, leakage report, and CI smoke subset.

## Repair log

The first validation pass correctly reported duplicate event IDs because the
smoke subset intentionally reuses eight formation records. The uniqueness
validator was narrowed to canonical partitions; the smoke subset remains an
explicit derived view and is independently hashed. No dataset record changed to
obtain this repair.

## Acceptance

- [x] Every row validates against Issue #7 contracts.
- [x] Every formation item belongs to a complete matching group.
- [x] Only declared treatment dimensions differ.
- [x] No shock, intervention, desired-answer, private-data, or secret finding
  appears in formation partitions.
- [x] Generation and partition hashes are deterministic.
- [x] Held-out partitions are marked and frozen.
- [x] Balance and manual review reports pass.
- [x] Known deterministic-semantic-scan limitation is documented.

## Validation evidence

- `generate_dataset.py --check` reproduced all 11 generated files and dataset
  SHA-256 `5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387`.
- The focused data suite passed ten tests; the integrated suite passed 75 tests
  with 86.68% branch-aware coverage.
- Schema drift, Ruff format/lint, strict mypy across 33 source files, and
  `git diff --check` passed.
- The supervisor validator accepted the expected artifact ID/path, Issue #7
  input evidence, and both workflow acceptance checks.
