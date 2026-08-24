# Issue #14 evaluation engine

## Outcome

The evaluation engine turns structured trajectory evidence into versioned,
auditable metric records and deterministic analysis inputs. It implements the
frozen `abp-metrics-v1` formulas without reading generated prose for actions,
facts, plans, or resource use.

This layer separates three states:

1. immutable raw observations and run status;
2. derived trajectory metrics with eligibility and missingness reasons;
3. paired block contrasts and aggregate statistical summaries.

The deterministic fixtures and offline matrix walk-through are engineering
validation only. They are not pilot or primary research results.

## Metric boundary

Each metric consumes only its declared structured inputs. A missing input never
becomes a zero. Records carry the valid numerator/denominator, value or explicit
missing reason, metric version, source run IDs, and a content hash.

- Actions are determined from structured action tags.
- Resource allocation uses the authoritative resource ledger.
- Retrieval intrusion uses selected memory IDs and tags.
- Facts and interpretations remain separate probes.
- Future-plan contamination uses structured plan IDs, not prose search.
- Language uses only the frozen deterministic language label.
- Language–action contradiction is computed only after both independently
  derived components are valid.
- Normalized opportunity cost requires explicit prospective `Q` values and
  `Q_range`; it is unavailable rather than guessed when the accepted harness
  does not provide them.

Recovery uses the frozen shock-day origin, paired neutral allocation, the
`0.10` threshold, two consecutive eligible days, and right censoring at day 15.

## Matrix and execution boundary

The primary design expands exactly four formations, four interventions, two
model families, and ten seeds into 320 collision-resistant run assignments.
The reduced pilot expands to 32 assignments. Run IDs bind the complete design
and source hashes so two behaviorally different assignments cannot collide.

The offline executor is resumable and idempotent:

- completed assignments are never duplicated;
- failed and invalid assignments remain visible;
- raw result pointers are immutable and hash-checked;
- call, trajectory, and wall-clock budgets fail closed;
- `live_calls_enabled=false` is mandatory for Issue #14 infrastructure
  acceptance.

## Statistical boundary

Repeated days are reduced to trajectory summaries before confirmatory
comparisons. Analysis utilities implement paired block contrasts, deterministic
seed-block bootstrap intervals, paired sign-flip randomization, standardized
paired effects, Holm correction, model-family strata, recovery risk sets, and
missingness/sensitivity outputs.

These utilities preserve null, contradictory, undefined, and incomplete
results. They do not choose exclusions or alternative thresholds based on an
observed direction.

## Gate 3 stop condition

Issue #14 may prepare provider-ready assignments but may not call a live model.
Gate 3 remains blocked until the supervisor records exact model revisions,
credentials/access, prompt and dataset hashes, maximum calls/tokens/cost/time,
and an explicit live-run authorization. Mock or fixture outputs cannot be
reported as model-family findings.

## Reproduction

```bash
uv run python scripts/generate_schemas.py --check
uv run pytest tests/evaluation
uv run ruff check src/affective_belief_persistence/evaluation tests/evaluation
uv run mypy src/affective_belief_persistence/evaluation
```

Repository-wide acceptance additionally runs the complete test and coverage
gate, schema/data drift checks, formatting, linting, and strict type checking.
