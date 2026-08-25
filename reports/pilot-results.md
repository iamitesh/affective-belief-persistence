# Pilot results

## Status

**Blocked before transport.** Issue #14 validates metric arithmetic, experiment
expansion, resume behavior, and analysis plumbing offline. Gate 3 now verifies
the exact 32-assignment plan and immutable upstream hashes, but no
preregistered live model family was called, so there are no pilot behavioral
estimates.

## Available engineering evidence

- Frozen metric fixtures exercise production metric code.
- The reduced design expands to 32 unique assignments.
- Invalid, missing, repaired, and censored records remain explicit.
- Deterministic analysis fixtures preserve paired blocks and repeated-measures
  boundaries.

These checks are not research results and cannot support H1–H6.

## Gate 3 requirements

The pilot requires exact model revisions, provider access, prompt and dataset
hashes, and approved call/token/cost/time limits. The eventual report must add
assigned/valid counts, malformed-output rates, model-family-specific estimates,
uncertainty, null results, and the Gate 3 review decision.

The current machine-readable blocker is
`artifacts/orchestration/gate-3.json`. It records zero started trajectories,
zero live calls, zero paid calls, and nine explicit preflight blockers. The
original call-cap conflict is resolved outcome-blind: the approved 3,200-call
ceiling covers 2,560 scheduled calls plus a 640-call repair/retry reserve. The
remaining call-budget blocker requires the complete authorization to select a
maximum between 2,560 and 3,200 and to supply token, cost, and runtime ceilings.
