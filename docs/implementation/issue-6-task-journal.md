# Issue #6 task journal: safety and claim boundaries

- Issue: [#6](https://github.com/iamitesh/affective-belief-persistence/issues/6)
- Status: Accepted for Gate 0
- Started: 2026-08-15
- Owner: safety and claims agent
- Repair attempts used: 0 of 2
- Input handoff: Issue #4 accepted literature, novelty, and terminology artifacts

## Task ledger

| Task | Status | Evidence |
| --- | --- | --- |
| Define permitted, cautionary, and prohibited wording | Completed | `docs/terminology-and-claims.md`; policy claim rules |
| Freeze five-level claim–evidence ladder | Completed | YAML evidence levels 1–5; no subjective-state level |
| Define allowed/prohibited data | Completed | `docs/data-governance.md`; machine data policy |
| Define synthetic/provenance declaration | Completed | template and strict runtime contract |
| Define secret, identifier, and privacy scans | Completed | context-aware regex rules and synthetic test fixtures |
| Exclude human-subject activity from MVP | Completed | policy stop condition and human-research evaluator |
| Restrict agent tools and external publication | Completed | default-deny action evaluator; self-approval false |
| Protect output and chain-of-thought privacy | Completed | permitted output list; private-reasoning stop rule |
| Map every mandatory stop condition | Completed | ten policy conditions with severity, actions, event, and status |
| Add machine-readable safety event | Completed | runtime `SafetyEvent` and committed JSON Schema |
| Add compatible artifact/workflow provenance | Completed | optional typed fields plus safety-critical enforcement |
| Add release checklist and #15 handoff | Completed | named evidence and nonauthorization statement |
| Review README, PRD, methodology/protocol, and release language | Completed with one README finding | review section in `docs/safety-and-claims.md` |
| Add adversarial claim examples | Completed | nine rejected/corrected examples |
| Run focused safety/orchestration tests | Completed | 23 passed |
| Run Ruff and strict mypy on changed Python | Completed | both passed |
| Run integrated full suite and schema drift | Pending integration | Deferred while Issue #5 owns shared schema generation |

## Critical decisions

1. Safety is a graph control, not a disclaimer. A match creates sanitized
   evidence and a deterministic block/escalation path.
2. The claim ladder ends at Level 5 generalization. Subjective feeling or
   consciousness has no admissible level.
3. Findings record hashes and rule IDs rather than matched content so incident
   evidence does not duplicate PII, credentials, or private reasoning.
4. Agent actions are default deny. Agents cannot approve or execute external
   publication, even when they authored every underlying artifact.
5. New safety fields are optional for serialized compatibility; safety-critical
   gates enforce their presence and current passed status.
6. Synthetic data requires a declaration and independent reviewer. “Synthetic”
   alone is not a privacy or provenance guarantee.
7. Human-subject activity is a separate future protocol and cannot inherit MVP
   authorization.
8. Regex scans are backed by manual review and cannot be weakened by an agent
   after a false positive.

ADR-0012 records the durable enforcement decision.

## Contract changes and compatibility

- Added optional `ArtifactContract.safety_provenance`.
- Added paired optional `WorkflowContract.safety_policy_id` and
  `safety_policy_version`.
- Added `safety_boundary_detected`, `safety_action_applied`, and
  `safety_resolved` workflow event types.
- Existing JSON/checkpoints remain readable because new fields have defaults.
- Safety-critical artifacts are rejected by `SafetyEvaluator` when provenance
  is missing, stale, or not passed.

## README/PRD review findings

- PRD: accepted terminology and boundaries are consistently present.
- README: the title is cautionary and needs immediate behavioral qualification.
- README Phase 1 uses “experienced attachment,” which must be replaced with an
  operational shared-memory/relationship-conditioned description before
  release or Gate 0 terminology acceptance.
- The safety agent intentionally did not edit shared README/PRD paths during the
  parallel Issue #5/#6 execution. The integration owner was notified.
- Issue #5 methodology, preregistration, metric specification, and analysis plan
  passed the claim-boundary review: they use observable outcomes, explicitly
  reject subjective/human-mechanism claims, require condition isolation, and
  wire Issue #6 safety events into pilot and primary stop rules.
- The release checklist is an internal evidence gate and explicitly cannot
  serve as agent authorization to publish.

## Test evidence

Focused commands executed from the repository root:

```text
uv run ruff check src/affective_belief_persistence/safety.py \
  src/affective_belief_persistence/orchestration/contracts.py \
  src/affective_belief_persistence/orchestration/events.py tests/safety

uv run mypy src/affective_belief_persistence/safety.py \
  src/affective_belief_persistence/orchestration/contracts.py \
  src/affective_belief_persistence/orchestration/events.py

uv run pytest tests/safety \
  tests/orchestration/test_control_edge_cases.py \
  tests/orchestration/test_contracts_and_controls.py
```

Result: Ruff passed; strict mypy passed; 23 tests passed. The focused schema test
compares the complete committed safety-event schema with the runtime model.
The global schema generator was intentionally not run during parallel Issue #5
schema work; the supervisor owns the integration drift run.

## Acceptance checklist

- [x] Machine-readable and human-readable policy agree on the safety boundary.
- [x] All eight mandatory stop conditions map to severity, ordered supervisor
  actions, a workflow event type, blocked/escalated status, and no auto-retry.
- [x] Allowed synthetic fixture passes.
- [x] Representative fake PII and placeholder-secret fixtures are rejected.
- [x] Synthetic declaration rejects false claims and self-review.
- [x] Prohibited subjective claim and an unsupported evidence level are rejected.
- [x] Protected-split leakage stops and escalates.
- [x] Unauthorized action and agent self-publication approval are rejected.
- [x] Private-reasoning marker stops and quarantines output.
- [x] Safety event serializes without copying matched content.
- [x] Human subjects are outside the MVP.
- [x] Issue #15 can audit named evidence artifacts.
- [x] Parent integration has regenerated all shared schemas after Issue #5.
- [x] Parent integration full tests, coverage, and `git diff --check` pass.
- [x] README terminology finding is repaired; Gate 0 is unblocked.

## Handoff to Issue #15 and release

Audit the policy/hash, safety events, declaration manifests, scan outputs,
condition-isolation evidence, action denials, claim checklist, unresolved
terminology findings, and this journal. Do not accept agent-authored external
publication approval. Do not release while any safety event is unresolved or a
safety-critical artifact lacks current provenance.

## Blockers and deviations

| Timestamp (UTC) | Item | Status | Resolution owner |
| --- | --- | --- | --- |
| 2026-08-15 | README used “experienced attachment” | Resolved: replaced with operational relationship-conditioned language | Parent supervisor |
| 2026-08-15 | Global generated schemas were stale during parallel #5 work | Resolved: regenerated and drift-checked after both agents became idle | Parent supervisor |

## Parent integration evidence

On 2026-08-15 the supervisor accepted policy
`abp-synthetic-research-safety@1.0.0`, policy-file SHA-256
`eef3c81302a16a1644933da2ee458ffb78f22d6aa79b34d89744fff8950cbe7c`,
and the machine-enforced stop mappings as Gate 0 evidence.
The integrated suite passed 65 tests with 86.42% branch-aware coverage; 18
generated schemas were current; Ruff formatting/lint and `git diff --check`
passed. Strict isolated mypy passed all 28 source files.
