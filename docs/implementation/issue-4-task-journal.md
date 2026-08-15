# Issue #4 task journal: literature and novelty map

- Issue: [#4](https://github.com/iamitesh/affective-belief-persistence/issues/4)
- Status: Accepted for Gate 0 handoff
- Started: 2026-08-15
- Accepted: 2026-08-15
- Owner: research and novelty agent
- Repair attempts used: 0 of 2

## Task ledger

| Task | Status | Evidence |
| --- | --- | --- |
| Define search protocol and criteria | Completed | `docs/literature-matrix.md`; search-log CSV |
| Search ten required evidence domains | Completed | 14 logged queries; 34 included records |
| Deduplicate versions and identifiers | Completed | Validation report: zero duplicate identifiers, URLs, or keys |
| Populate required machine-readable schema | Completed | 34 JSONL records × 25 required fields |
| Separate human and model evidence | Completed | Coverage table and per-row source type |
| Compare closest five to ten works | Completed | Ten-row closest-work table |
| Map overloaded terminology | Completed | `docs/terminology-map.md` |
| Record contradictory/null evidence | Completed | Matrix field and review register |
| Draft three novelty statements | Completed | Ambitious, moderate, conservative |
| Select strongest defensible statement | Completed | Conservative statement selected |
| Validate citations and fields | Completed | `docs/literature-validation-report.md` |
| Supervisor acceptance | Completed | All Issue #4 acceptance criteria checked |

## Critical decisions

1. Novelty is claimed for a **measurable experimental combination**, not for
   memory, social agents, role-play, trajectory adaptation, or “machine love.”
2. The recommended statement avoids “first” and remains valid if the empirical
   result is null.
3. Human attachment, dissonance, sunk-cost, autobiographical-memory, and
   reconsolidation research provides manipulation inspiration only.
4. Relationship-conditioned structured action and opportunity cost are primary;
   generated emotional language is secondary.
5. Fact, interpretation, retrieval, instructions, explicit belief state, and
   parameters are separate causal layers.
6. A second forward/backward citation pass is mandatory before submission; the
   initial matrix is sufficient for Gate 0 but not proof of exhaustive novelty.

ADR-0010 records the durable positioning decision.

## Deliverables

- `docs/literature-matrix.md`
- `data/research/literature-matrix.jsonl`
- `data/research/literature-search-log.csv`
- `docs/novelty-and-positioning.md`
- `docs/terminology-map.md`
- `docs/research-citations.bib`
- `docs/literature-validation-report.md`
- `docs/decisions/0010-measurable-non-anthropomorphic-novelty.md`

## Handoff to Issues #5 and #6

Methodology must implement the ten controls listed in the positioning document,
use the conservative novelty statement, and map each hypothesis to structured
behavior. Safety must enforce the terminology map and make the unavailable
subjective-state claims machine-rejectable.

## Deviations and unresolved risk

- Direct automated resolution of some publisher DOI and OpenReview pages was
  blocked by anti-bot controls. Their identifiers were confirmed through primary
  indexes/search results and are marked crawler-unresolved in the validation
  report, not silently treated as healthy.
- The search is a timeboxed Gate 0 pass. It must be refreshed before submission,
  especially for 2025–2026 relationship-memory and socioaffective work.

