# ADR-0024: Approve an outcome-blind 3,200-call Gate 3 pilot ceiling

- Status: Accepted
- Date: 2026-08-25
- Scope: Issue #27 pilot call ceiling only

## Context

Gate 3 preflight found that the original 1,600-call ceiling could not execute
the already-frozen protocol. Each of 32 assignments has 40 trajectory days,
and each day separates action inference from public-language inference. The
minimum is therefore `32 × 40 × 2 = 2,560` provider calls before any bounded
repair or transport retry.

No pilot trajectory had started, no live or paid call had occurred, and no
behavioral outcome had been generated or inspected when the research owner
approved a 3,200-call ceiling.

## Decision

1. Approve 3,200 as the hard operational model-call ceiling for the Gate 3
   exploratory pilot.
2. Allocate 2,560 calls to the frozen two-stage schedule and 640 calls, or 25%
   of that minimum, as the combined repair/retry reserve.
3. Preserve the 32 assignments, 40 days, two provider stages, matrix identity,
   hypotheses, metrics, thresholds, and expansion rules.
4. Keep `configs/experiments/pilot.yaml` unchanged as the accepted Issue #14
   source record. Apply the narrow supersession through the typed, hash-bound
   `configs/gate3/call-budget-amendment.yaml` record.
5. Treat this approval as call-cap change control only. It does not authorize a
   provider, credential, model revision, tokens, cost, runtime, or transport.
6. Require the later complete authorization to choose a call budget between
   2,560 and 3,200. Preflight blocks anything outside that range.

## Consequences

- The protocol is operationally feasible without changing its scientific
  design or silently rewriting the accepted experiment configuration.
- The amendment and authorization both bind the amendment file SHA-256, so
  later byte drift blocks before transport.
- Unused reserve does not authorize additional trajectories, longer schedules,
  exploratory cells, or primary execution.
- Gate 3 remains blocked until all other authorization and runtime checks pass.

## Verification

- A strict generated schema fixes the arithmetic and prohibits outcome or call
  claims in the amendment record.
- Preflight verifies that the amendment applies to the original 1,600-call cap
  and the exact 32 × 40 × two-stage design.
- The committed blocked artifact reports zero trajectories and zero calls.

## References

- [Issue #27](https://github.com/iamitesh/affective-belief-persistence/issues/27)
- [Gate 3 pilot boundary](../gate-3-pilot.md)
- [ADR-0023](0023-explicit-hash-bound-gate-3-authorization.md)
