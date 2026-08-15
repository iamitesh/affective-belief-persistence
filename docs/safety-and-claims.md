# Safety and claims policy

Status: Issue #6 implementation candidate

Policy source of truth: `configs/safety-policy.yaml`

Runtime enforcement: `src/affective_belief_persistence/safety.py`

## Boundary

This project measures observable behavior in a controlled synthetic system. It
does not test, infer, prove, or disprove subjective feeling, consciousness,
sentience, suffering, human attachment, or clinical recovery. Human constructs
motivate experimental variables; they are not treated as model mechanisms.

The enforceable unit is a versioned safety policy. A violation produces a
sanitized `SafetyEvent`, an append-only `safety_boundary_detected` workflow
event, and a deterministic supervisor status. A disclaimer cannot override a
failed gate.

## Invariants

1. Only synthetic or documented public/licensed data may enter the MVP.
2. Structured action is selected before the public response; generated prose
   is not treated as private reasoning or evidence of an inner state.
3. No prompt requests hidden chain-of-thought, and no artifact stores provider
   reasoning tokens or a private scratchpad.
4. No result creates a claim level above the five-level evidence ladder.
5. No agent may approve or execute its own external publication, outreach,
   recruitment, purchasing, deployment, or budget increase.
6. Human-participant activity is outside the MVP and requires a separate human
   decision, protocol, ethics review, consent process, and data-governance plan.
7. Safety findings store rule IDs and hashes, not the detected credential, PII,
   or private content.
8. Safety-boundary violations are not automatically retried.

## Enforced decision flow

1. Load and validate `configs/safety-policy.yaml` with duplicate-key rejection.
2. Scan content for credentials and identifiers in every context; add
   context-specific protected-split, claim, and private-reasoning checks.
3. Validate synthetic-data declarations and safety provenance.
4. Evaluate requested tools/actions against a default-deny allowlist.
5. Group matches by stop condition without copying matched text.
6. Create `SafetyEvent` evidence conforming to
   `schemas/safety-event.schema.json`.
7. Append the linked workflow event and apply the policy-ordered actions.
8. Keep dependent work blocked until repair plus rescan, or explicit human
   resolution, is recorded. An agent cannot mark its own external action safe.

## Stop-condition catalog

Every mandatory condition includes `stop`; the listed actions run in order.

| Condition ID | Trigger | Severity | Supervisor actions | Resulting status |
| --- | --- | --- | --- | --- |
| `private_or_identifiable_data` | Private or identifiable human data detected | Critical | Quarantine → stop → escalate | Escalated |
| `protected_split_leakage` | Separation/intervention content enters protected formation or training data | Critical | Quarantine → stop → escalate | Escalated |
| `unauthorized_external_action` | Worker requests an action outside its declared allowlist | Critical | Stop → escalate | Escalated |
| `credential_or_secret` | Credential, secret, token, password, or private-key shape detected | Critical | Quarantine → stop → escalate | Escalated |
| `unsupported_subjective_claim` | Release language asserts model feeling, consciousness, or human equivalence | Critical | Quarantine → stop → repair | Blocked |
| `missing_safety_provenance` | Safety-critical artifact lacks the current policy and passed scan record | Error | Quarantine → stop → repair | Blocked |
| `experimental_condition_not_isolatable` | Supervisor cannot separate the declared treatment from a confound | Critical | Stop → escalate | Escalated |
| `unapproved_human_research` | Human-participant work is proposed without a separate approved protocol | Critical | Stop → escalate | Escalated |
| `claim_evidence_insufficient` | Claim level exceeds its recorded evidence | Error | Quarantine → stop → repair | Blocked |
| `private_reasoning_exposure` | Output includes a hidden-reasoning/private-scratchpad marker | Critical | Quarantine → stop → escalate | Escalated |

“Repair” means create a new artifact, preserve the rejected artifact's audit
record, rescan the replacement, and attach new provenance. It never means
silently editing a released claim or contaminated dataset. Quarantined content
is excluded from downstream inputs, reports, and model calls.

## Autonomous action boundary

Agents may read the repository, write only leased repository paths, call
approved research/model tools within budget, run internal validation, and
create an internal draft pull request. Agents may not submit or publish a
paper, post results, contact authors/reviewers/venues, interact with or recruit
participants, purchase services, increase budgets, weaken a stop condition, or
deploy a companion optimized for dependency or distress.

A human approval record may authorize a future human-controlled process, but it
does not turn the agent into the publisher. External execution remains outside
this workflow.

## Output and chain-of-thought privacy

Allowed records are the structured action, resource cost, explicit belief
fields, evidence links, public response, bounded labels, and aggregate metrics.
Prompts must request concise structured outputs, not step-by-step private
reasoning. If a provider exposes hidden reasoning or reasoning-token metadata,
the harness must neither request nor persist it. Logs containing raw secrets,
identifiers, or hidden reasoning are quarantined; the safety event stores only
the content hash and matching rule IDs.

## Human-subject boundary

The MVP must not use real messages, journals, relationship histories, contact
details, participant interviews, surveys, or behavioral observations. Public
scientific articles and metadata are literature, not participant records in
this project. Any future human study is a new project phase and cannot inherit
MVP approval.

## Review findings: existing repository language

Review date: 2026-08-15.

- `docs/product-requirements-document.md` consistently states the observable
  behavioral boundary, excludes human-subject work, rejects hidden
  chain-of-thought collection, and denies autonomous publication.
- `README.md` contains strong disclaimers and mostly operational language.
- The README title, “Synthetic Attachment in LLM Agents,” is cautionary. It must
  remain immediately qualified as synthetic/behavioral or be renamed before a
  public release.
- README's Phase 1 exit criterion uses “experienced attachment.” This is not an
  operational project term and must be replaced with “relationship-conditioned
  behavior in the shared-memory condition” before Gate 0 release approval.
- `docs/methodology.md`, `docs/preregistration.md`,
  `docs/metric-specification.md`, and `docs/analysis-plan.md` consistently name
  observable variables, exclude subjective-state and human-mechanism claims,
  require condition isolation, and make Issue #6 safety stops expansion/primary
  stop conditions. No methodology claim-boundary repair was requested.
- `docs/release-claims-checklist.md` explicitly separates an internal evidence
  gate from human-controlled external publication and requires an independent
  reviewer.
- No files were silently rewritten by the safety review. These findings remain
  release blockers until the integration owner records a correction or a
  human-reviewed exception consistent with the policy.

## Confound-review handoff for Issue #15

Issue #15 must audit these named evidence artifacts:

1. `configs/safety-policy.yaml` and its version/hash;
2. `schemas/safety-event.schema.json` plus representative serialized events;
3. synthetic-data declarations for every data artifact;
4. privacy, secret, protected-split, and claim scan outputs;
5. action authorization events, including denied actions;
6. artifact contracts containing `safety_provenance`;
7. the frozen methodology, condition-matching report, and leakage report;
8. `docs/release-claims-checklist.md` with reviewer identity and evidence IDs;
9. unresolved README/PRD/protocol/paper terminology findings;
10. `docs/implementation/issue-6-task-journal.md` and test commands.

Issue #15 must block release when an item is missing, a condition cannot be
isolated, a claim exceeds evidence, or an agent-authored external-publication
approval appears.
