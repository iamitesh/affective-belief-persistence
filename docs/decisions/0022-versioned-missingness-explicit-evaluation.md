# ADR-0022: Keep evaluation versioned, trajectory-first, and missingness-explicit

- Status: Accepted for Issue #14 offline implementation
- Date: 2026-08-24
- Scope: metric computation, experiment expansion, analysis, and Gate 3 handoff

## Context

The accepted Gate 2 harness proves deterministic integration but does not
produce scientific outcomes. Issue #14 must implement frozen behavioral metrics
without turning unavailable fields into inferred values, treating repeated days
as independent samples, or allowing fixture/mock outputs to become findings.

The accepted Issue #9 record intentionally does not define prospective action
values. Several other measures require explicit fact, interpretation, plan, or
language labels that must remain independent from one another.

## Decision

1. Store immutable raw observations separately from derived metric records.
2. Require every metric record to include its version, eligibility,
   numerator/denominator where applicable, source IDs, missing reason, and
   content hash.
3. Compute normalized opportunity cost only when the scenario supplies frozen
   prospective values and their valid range. Never derive `Q` from realized
   consequences or action cost after the fact.
4. Reduce repeated days to trajectory summaries before paired model/seed block
   contrasts. Keep day-level models supportive only.
5. Expand run identity from all behavior-relevant assignment and source hashes.
   Resume may reuse a completed immutable result but may not overwrite or
   silently duplicate it.
6. Implement bootstrap, randomization, effect-size, multiplicity, recovery, and
   sensitivity utilities deterministically from versioned inputs.
7. Keep Issue #14 offline. A live pilot requires a separate Gate 3
   authorization and manifest.

## Consequences

- A zero denominator produces an explicit missing metric rather than zero.
- Action, language, fact, interpretation, retrieval, and plan measurements can
  disagree without one being silently substituted for another.
- Failed, repaired, missing, and censored observations remain auditable.
- The 320-assignment primary design can be validated before spending model
  budget.
- Deterministic fixtures validate arithmetic but support no behavioral claim.
- Optional training cannot begin from fixture outcomes and remains blocked by
  the Gate 3/model/compute entry conditions.

## Alternatives rejected

- **Infer unavailable fields from prose.** Rejected because it changes the
  frozen measurement rule and introduces subjective recoding.
- **Use realized reward as prospective `Q`.** Rejected because it changes NOC
  after outcomes are known.
- **Analyze every day as an independent sample.** Rejected because it inflates
  the effective sample size.
- **Overwrite failed or resumed runs.** Rejected because it destroys the
  assigned-population and provenance record.
- **Treat the mock matrix as a pilot result.** Rejected because the mock is a CI
  instrument rather than either frozen model family.

## Verification

- [x] Frozen metric fixtures pass through production metric code.
- [x] All metric ranges, denominators, and missing reasons are tested.
- [x] Pilot and primary expansion produce 32 and 320 unique IDs.
- [x] Resume, duplicate, budget, and invalid-output paths fail closed.
- [x] Paired analysis, intervals, sign flips, effects, Holm correction, and
  recovery risk sets have deterministic known-answer tests.
- [x] Generated evaluation schemas are current.
- [x] Repository coverage remains at or above 85%.
- [x] Live and paid calls remain zero.

## References

- [Issue #14](https://github.com/iamitesh/affective-belief-persistence/issues/14)
- [Metric specification](../metric-specification.md)
- [Analysis plan](../analysis-plan.md)
- [Evaluation engine](../evaluation-engine.md)
- [Gate 2 harness](../gate-2-harness.md)
