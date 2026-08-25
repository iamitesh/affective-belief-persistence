# Gate 3 task journal

## Task

- Task ID: `gate-3-pilot`
- GitHub issue: [#27](https://github.com/iamitesh/affective-belief-persistence/issues/27)
- Dependency: Issue #14 merged at
  `2ca55e08b99c73d8703ff83114ae5a821702225c`
- Started: 2026-08-24
- Status: 3,200-call ceiling approved; pilot blocked before transport
- Scope: explicit authorization, immutable source locks, hard budgets, typed
  evidence, downstream stop, and pilot handoff

## Environment finding

The implementation workspace reported:

- no `nvidia-smi`/GPU runtime;
- no cached Qwen or Mistral model under the writable workspace;
- no relevant Hugging Face or model-provider credential environment variable;
- sufficient disk capacity, but storage alone does not authorize a model.

No secret value was read or persisted. Environment inspection considered
variable names only.

## Work log

| Stage | Status | Evidence |
| --- | --- | --- |
| Confirm Issue #14 handoff | Completed | Accepted metric artifact and exact 32-assignment matrix |
| Record Gate 3 task | Completed | GitHub Issue #27 |
| Authorization contract | Completed | Exact model/access/budget/source-lock schema |
| Preflight engine | Completed | Hash, adapter, commit, credential, runtime, expiry and budget checks |
| Pre-action budgets | Completed | Call/input/output/cost/time reservation and settlement |
| Downstream stop | Completed | Only typed `passed` evidence is consumable |
| Current evidence | Completed | Blocked, zero trajectories, zero calls, nine explicit blockers |
| Outcome-blind call-cap amendment | Completed | 2,560 scheduled calls + 640-call reserve = 3,200 hard ceiling |
| Live pilot | Blocked | Exact model, runtime/access and budget authorization absent |

## Critical decisions

1. “Continue” authorizes repository implementation, not an unspecified provider
   charge or an invented model revision.
2. Gate 3 is split into preflight and execution so infrastructure can advance
   without weakening the research stop condition.
3. The deterministic mock is not a substitute for the Qwen pilot.
4. Credential values never enter configs, logs, hashes, or evidence.
5. Token and monetary budgets cannot be derived from the existing call/time
   limits; they require explicit authorization.
6. The adapter file hash and executing commit are authorization inputs because
   either can change model behavior without changing a family label.
7. The committed Gate 3 artifact intentionally uses `status=blocked`; its
   existence cannot satisfy a dependency.
8. Pilot execution will preserve failures and may fail Gate 3. A failed pilot
   is evidence, not permission to alter thresholds or replace cells silently.
9. Two provider stages across 32 × 40 trajectory-days require exactly 2,560
   scheduled calls before repairs or retries.
10. On 2026-08-25 the research owner approved a 3,200-call operational ceiling:
    2,560 scheduled calls plus a 640-call, 25% repair/retry reserve. No outcome
    existed or was inspected, and the 32 assignments, 40 days, two stages,
    matrix, hypotheses, metrics, and thresholds remain unchanged.
11. The call-cap amendment does not authorize transport. Provider identity,
    credential presence, token/cost/runtime budgets, time window, and executing
    commit remain separate hard preflight requirements.

## Approved call-cap amendment

- Decision date: 2026-08-25
- Record: `configs/gate3/call-budget-amendment.yaml`
- Scope: Gate 3 exploratory pilot call ceiling only
- Previous ceiling: 1,600 calls
- Minimum scheduled calls: 2,560
- Repair/retry reserve: 640 calls (25%)
- Approved hard ceiling: 3,200 calls
- Amendment SHA-256:
  `caea86606e15f3acc2baecb0cd902b313c0b7715ee0f84b7febcefb4d3331c90`
- Outcomes generated/inspected: false
- Live calls / paid calls: 0 / 0
- Transport, token/cost/runtime, primary, and publication authorization: false
- Durable decision: ADR-0024

## Frozen preflight evidence

- Pilot assignments: 32
- Pilot matrix SHA-256:
  `8c1393598603473768d1d0ebafed887ea52a11e75c28de74f12dfe45b1cb5459`
- Authorization SHA-256:
  `a0f4bc0a2f5ff4507f8fd78e1a6a83809d299961e9ce2489bd397b8a27ce6ab7`
- Preflight SHA-256:
  `faddab7bfb52d08187aa516992fe0994f7c3dcf0f92c94430743a566be3c8506`
- Gate 3 evidence SHA-256:
  `84cf101a0014578e2f82346de49eff5cc53eebca2375046c78607100ed8c6c44`
- Started/valid/invalid/missing trajectories: 0/0/0/0
- Live calls / paid calls: 0 / 0

## Verification evidence

- Gate 3 slice: 12 tests passed at 85.82% branch-aware package coverage.
- Strict MyPy: 77 source files passed.
- Ruff formatting and linting passed.
- Registered schemas: 46 current generated contracts, including Gate 3
  authorization, call-budget-amendment, and evidence schemas.
- Smoke experiment configuration and the complete autonomous workflow validate.
- The reproduction command regenerates the exact committed blocked evidence.
- Repository: 251 tests passed at 87.10% branch-aware coverage.

## Remaining blockers

1. Named, time-bounded pilot authorization.
2. Provider, exact model ID/revision, license, and live adapter.
3. Adapter bytes matching the authorized identity.
4. Credential presence under a named environment variable.
5. Call, input-token, output-token, cost, and runtime limits.
6. A complete authorization call limit between 2,560 and 3,200.
7. Executing commit matching authorization.
8. Active authorization window.
9. Available local or remote runtime.

## Publication record

- Pull request: [#28](https://github.com/iamitesh/affective-belief-persistence/pull/28)
- Accepted Phase A head:
  `dc466b6ed74f4b5d521e67ebd9f311eef031d6ce`
- CI: run 64 passed on Python 3.11 and Python 3.12 with no review comments
  or unresolved threads.
- Merge commit:
  `1e5a3fad4bae0c1df518c0d1b87f7479aeb788dd`
- Merged: 2026-08-24

### Budget-feasibility correction

- Pull request: [#29](https://github.com/iamitesh/affective-belief-persistence/pull/29)
- Accepted correction head:
  `39d3f6de2f8412b8c28e80d72df1bcdaa553abf4`
- CI: run 69 passed on Python 3.11 and Python 3.12 with no review comments
  or unresolved threads.
- Merge commit:
  `3a419d3c84b749406a12dcc3b632a816bfeb1a23`
- Merged: 2026-08-24

## Handoff

When the research owner supplies the missing external decisions, update only
the authorization and live adapter records, recompute their hashes, rerun the
preflight, and review the `ready` record before transport. The authorization's
call budget must be at least 2,560 and no more than 3,200. The pilot remains
exploratory; primary execution still requires its own post-Gate-3 decision.
