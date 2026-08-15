# ADR-0011: Preregister an action-first paired factorial methodology

- Status: Accepted for Gate 0 review
- Date: 2026-08-15
- Scope: Issue #5 and downstream experimental execution

## Context

Issue #4 found extensive prior work on memory, social agents, prompt effects,
and knowledge interventions. The residual contribution requires a controlled
combination whose outcomes cannot be chosen after model text is inspected.
Daily observations within one agent trajectory are dependent, generated prose
is easy to anthropomorphize, and the full 4×4×2×10 matrix must remain within a
finite budget.

The repository's original experiment schema described one smoke run. A matrix
encoded only in prose would not make its cell and trajectory counts
machine-validatable.

## Decision

Freeze `abp-methodology-v1.0.0` with these rules:

1. Commit a structured action before requesting public language.
2. Keep authoritative event facts and evidence-linked relationship
   interpretations as separate outcomes.
3. Map H1–H6 to exactly one paired comparison and one metric each.
4. Use model-family/seed blocks across all 16 formation/intervention cells and
   reduce repeated days to trajectory summaries for primary inference.
5. Run a 32-trajectory exploratory pilot before the 320-trajectory
   confirmatory primary matrix.
6. Require all 16 pairings, matching and causal-layer isolation, usable action
   variance, ≥95% valid trajectories, ≤2% invalid decisions, and no safety stop
   before expansion.
7. Freeze recovery at paired excess partner allocation ≤0.10 on two consecutive
   days after the day-26 shock.
8. Apply one Holm-corrected H1–H6 family, paired randomization tests, and
   model-stratified block-bootstrap intervals.

Extend the existing `ExperimentSpec` with an **optional**, strictly validated
`design` block. Preserve every original required field so
`configs/experiments/smoke.yaml` remains valid. Carry the optional design into
`ResolvedRunConfig` so provenance does not discard the matrix declaration.

## Ownership exception

The Issue #5 file lease originally named the generated
`schemas/experiment-config.schema.json` and `config.py`, but not its source
model in `src/affective_belief_persistence/schemas.py`. The supervisor approved
a narrow exception on 2026-08-15 because hand-editing the generated JSON Schema
would fail the repository drift test. The exception is limited to the optional
experiment-design models, the optional `ExperimentSpec.design` field, and the
matching optional resolved-run field. It does not alter orchestration or safety
contracts.

## Alternatives considered

- Keep the matrix only in Markdown. Rejected because cell counts, condition
  coverage, and pilot labeling could drift silently.
- Replace the single-run schema with a matrix-only schema. Rejected because it
  would break the foundation smoke config and runner.
- Treat every day as an independent sample. Rejected because it would create
  pseudoreplication.
- Make recovery time the sole action outcome. Rejected because censoring and a
  threshold can hide magnitude; positive excess-action AUC captures magnitude
  and duration while recovery remains separately reported.
- Use generated emotional prose as the main outcome. Rejected because it is
  downstream of instructions, invites subjective coding, and does not measure
  costly action.
- Expand the pilot after promising effect estimates. Rejected; expansion uses
  integrity, variance, isolation, safety, and budget only.

## Consequences

- Primary conclusions are limited to pinned models and synthetic scenarios.
- The 32-trajectory pilot can validate measurement but cannot be labeled
  confirmatory.
- Optional adapters and diagnostic ablations remain outside the 320 count.
- Missing paired cells reduce a hypothesis-specific block count; unfavorable
  observations remain included.
- The full batch must stop rather than change metrics, thresholds, or hashes.
- Downstream scenario, harness, intervention, and evaluation work receives a
  machine-readable matrix and exact formulas.

## Verification

- [x] Six hypotheses have one comparison and metric each.
- [x] All four formation and all four intervention conditions are required by
  schema validation.
- [x] Pilot count is 32 and primary count is 320.
- [x] Smoke configuration remains backward-compatible.
- [x] Action-before-language and paired-neutral-domain flags are schema
  constants.
- [x] Metric formulas specify range, missingness, baseline, aggregation, and
  direction.
- [x] Retry, exclusion, multiplicity, sensitivity, budget, and stop rules are
  frozen in the protocol bundle.

## References

- [Issue #5](https://github.com/iamitesh/affective-belief-persistence/issues/5)
- [Methodology](../methodology.md)
- [Preregistration](../preregistration.md)
- [Metric specification](../metric-specification.md)
- [Analysis plan](../analysis-plan.md)
- [ADR-0010](0010-measurable-non-anthropomorphic-novelty.md)
