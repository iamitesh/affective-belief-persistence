# Gate 3 pilot authorization and preflight

## Current outcome

Gate 3 is **blocked before transport**. The frozen pilot matrix contains 32
unique assignments and all accepted upstream hashes match, but the workspace
does not contain the external facts needed to authorize a real model run.

The research owner approved an outcome-blind operational ceiling of 3,200
model calls on 2026-08-25. The ceiling covers the 2,560 calls required by 32
trajectories × 40 days × two provider stages plus a 640-call, 25% repair/retry
reserve. `configs/gate3/call-budget-amendment.yaml` records the narrow change.
It preserves the assignments, days, provider stages, thresholds, and outcomes.
It supersedes only the original 1,600-call pilot ceiling.

This call-cap approval is not transport authorization and is not a successful
pilot. It generated no behavioral results and made zero live or paid calls.

## Required authorization

`configs/gate3/pilot-authorization.yaml` is the only Gate 3 authorization
record. To change its decision to `approved`, the research owner must supply:

- provider and exact Qwen-compatible model ID;
- a full immutable revision and license identifier;
- a live-enabled adapter config plus its SHA-256;
- the executing Git commit;
- a credential environment-variable name, never its value;
- a maximum-call budget between 2,560 and 3,200, plus input-token,
  output-token, estimated-USD-cost, and runtime ceilings;
- named authorizer, approval time, and expiry time.

Approval authorizes only the 32-trajectory exploratory pilot. It does not
authorize the 320-trajectory primary batch, training, external publication, or
subjective-state claims.

## Preflight checks

Before transport, the implementation recomputes and compares:

1. accepted Gate 1, Gate 2, and Issue #14 evidence;
2. evaluation and pilot configuration hashes;
3. dataset-manifest, prompt-bundle, and metric-code hashes;
4. the exact 32-assignment matrix hash;
5. the approved amendment bytes and its 32 × 40 × two-stage arithmetic;
6. adapter bytes and provider/model/revision/prompt fields;
7. executing Git commit, credential presence, runtime availability, and active
   authorization window;
8. hard call, token, cost, and time budgets;
9. feasibility of the authorized call budget against the 2,560–3,200 range.

Any mismatch blocks before a model request. No threshold is repaired after an
outcome is visible.

## Reproduce the current blocker

```bash
uv run python scripts/gate3_preflight.py \
  --expect-status blocked \
  --check-artifact artifacts/orchestration/gate-3.json
```

The command prints the preflight record and verifies that
`artifacts/orchestration/gate-3.json` is the exact expected blocked evidence.

## Pilot pass boundary

A future passed artifact requires the real pilot to start all 32 assignments,
retain at least 95% valid trajectories, quantify malformed and repaired
outputs, cover every factorial cell, preserve action variance, pass condition
isolation and safety checks, and record exact usage. Language and action remain
separate. Mock or fixture output cannot satisfy this boundary.

Only `Gate3Evidence(status="passed")` unlocks downstream execution. A blocked
or failed artifact raises a hard error even if its path and artifact ID exist.
