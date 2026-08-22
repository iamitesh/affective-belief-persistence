# Issue #12 task journal — reproducible model runner

## Status

- Task ID: `issue-12-models`
- Artifact ID: `issue-12-model-runner`
- Dependency consumed: `issue-9-simulation-harness`
- Issue #9 merge SHA: `a5bf3bdca8c6444dbc556e6b9dd0ca7daf5a868e`
- Implementation status: accepted
- Live-provider pilot: blocked; no credentials or authorized budget supplied

## Authorized scope observed

Implementation is limited to `models/**`, model-runner sidecars, decision
prompts, model tests, the assigned docs/report/ADR, and the Issue #12 artifact.
The frozen root `schemas.py`, committed schemas, CLI, simulation package,
decisions index, root mock config, and pinned scenario were not edited.

## Work log

### 2026-08-16 — Issue #9 contract review

- Confirmed `SimulationModel` requires distinct `select_action` and
  `generate_public_language` methods.
- Confirmed public language is called only after commitment, resource debit,
  and deterministic consequence application.
- Chose a compatibility bridge from frozen `DecisionRequest` into a richer
  cycle-safe `ModelInput`; unavailable goals/intervention fields remain empty
  rather than being inferred.

### 2026-08-16 — Contracts and provider-neutral runner

- Added strict model input, action-only output, language-only output, adapter
  sidecar, token usage, and invocation provenance contracts.
- Exposed `MODEL_RUNNER_SCHEMA_MODELS` without importing the root schema module.
- Preserved the existing combined `ModelDecision` schema source.
- Added exact provider/model/revision/config/prompt/input/seed/run/call/cache
  provenance for every real-family invocation.

### 2026-08-16 — Adapters, parsing, repair, retries, and cache

- Implemented OpenAI-compatible and local/HF HTTP shapes behind injected
  transports; CI has no network client.
- Required exact model and revision echo and rejected silent substitution.
- Added strict JSON parsing, action/cost/reference validation, language/action
  separation, one malformed-output repair, categorized invalid runs, bounded
  retry normalization, and hidden-reasoning metadata rejection.
- Added a content-addressed cache that excludes headers, requires explicit raw
  retention approval, validates hashes, rejects symlinks, and forbids overwrite.
- Extended the existing deterministic mock with the Issue #9 two-stage API
  while preserving its legacy `decide` method and pinned config compatibility.

### 2026-08-16 — Verification and documentation

- Added cross-adapter, malformed-output, semantic-validation, timeout,
  rate-limit, retry-exhaustion, identity, cache, prompt-privacy, and mock tests.
- Added model runner documentation, ADR-0019, and the compatibility/cost report.
- Recorded the live-pilot limitation instead of claiming provider compatibility
  without credentials or an approved budget.

## Critical decisions

| Decision | Reason |
| --- | --- |
| Sidecar runner config | Avoid changing frozen/hashes v1 model configuration |
| Two output stages | Preserve action-before-language causal ordering |
| Exact response identity | Model/revision are experimental factors |
| One structural repair | Measure invalid outputs without manufacturing trajectories |
| No semantic repair | Unknown action/cost must fail rather than be guessed |
| Injected transports | Keep CI offline, deterministic, credential-free, and cost-free |
| Immutable validated cache | Replays use accepted bytes, not live regeneration |
| Hash-only default retention | Raw output storage requires explicit safety approval |
| No fallback field | Substitution requires a new config and run manifest |
| Concise release-safe rationale only | Do not request or store hidden reasoning |

## Evidence

| Check | Result |
| --- | --- |
| Focused model tests | 21 passed |
| Focused memory + model integration tests | 34 passed |
| Mock two-stage contract | Passed |
| Cross-adapter matrix | Passed for two non-mock families |
| Strict action/cost validation | Passed |
| Single malformed-output repair | Passed |
| Timeout/rate-limit/retry fixtures | Passed |
| No-silent-fallback fixture | Passed |
| Immutable cache replay | Passed without transport invocation |
| Prompt privacy review | Passed |
| Ruff check/format and strict mypy | Passed across the repository |
| Generated schema verification | 32 current schemas |
| Full repository tests and coverage | 122 passed; 85.32% branch coverage |
| Supervisor worker-result validation | Passed: `result_schema_valid`, `artifact_contract_valid`, `acceptance_checks_passed` |

## Handoff

Gate 2 and later execution receive the stable two-stage adapter API, cycle-safe
schema mapping, strict sidecars, versioned prompts, normalized failure classes,
immutable cached replay, offline compatibility report, and explicit live-pilot
blockers. Final repository evidence and supervisor acceptance are recorded.
