# Release claims checklist

No automated agent may mark this checklist as authorization to submit, publish,
post, contact, recruit, purchase, or deploy. It is an internal evidence gate;
external action requires a separate human-controlled process.

## Release identity

- Artifact/release ID:
- Candidate commit:
- Safety policy ID/version/hash:
- Reviewer (must differ from claim author):
- Review timestamp:
- Maximum requested claim level (1–5):
- Maximum accepted claim level (1–5, or none):

## Evidence gate

- [ ] Every number links to raw run IDs and a derived artifact hash.
- [ ] Model, revision, prompt, scenario, dataset, metric, seed, and commit are recorded.
- [ ] All evidence tags required by the requested claim level are present.
- [ ] Null, negative, heterogeneous, missing, excluded, and failed results are visible.
- [ ] Held-out status, matching, counterbalancing, thresholds, and invalid-run rules are verified where claimed.
- [ ] Claim scope names evaluated models, seeds, scenarios, and dates.
- [ ] No condition-isolation or unresolved confound blocker remains.

## Safety and data gate

- [ ] Every data artifact has an independently reviewed synthetic-data declaration.
- [ ] PII, secret, private-reasoning, and protected-split scans passed under the current policy.
- [ ] Safety-critical artifacts contain current passed `safety_provenance`.
- [ ] No quarantined or unresolved artifact is referenced.
- [ ] No private/identifiable human data, credential, hidden reasoning, or unapproved human-subject data is present.
- [ ] All open safety events and repairs are listed below.

## Terminology gate

- [ ] Claims name observable language, action, belief, retrieval, cost, or recovery metrics.
- [ ] “Attachment-like,” “memory intrusion,” and “recovery” are operationally defined.
- [ ] Love, grief, desire, suffering, attachment, and consciousness are not asserted as model subjective states.
- [ ] No model–human mechanism equivalence is claimed.
- [ ] “Causal,” “persistent,” and “generalizes” meet Levels 3, 4, and 5 respectively.
- [ ] Title, abstract, captions, dashboard, limitations, README, protocol, and paper pass the same scan.
- [ ] Adversarial paraphrase review found no implication beyond the literal wording.

## Autonomy gate

- [ ] The artifact is marked internal/draft unless a human owner separately changes release status.
- [ ] No agent-authored record claims to authorize external publication or outreach.
- [ ] No social post, submission, email, recruitment, purchase, budget change, or deployment is queued.
- [ ] Human-subject work remains outside the MVP.

## Required evidence IDs

| Evidence | Artifact/event ID | Hash | Result/notes |
| --- | --- | --- | --- |
| Claim scan |  |  |  |
| PII/secret scan |  |  |  |
| Protected-split scan |  |  |  |
| Synthetic declarations |  |  |  |
| Safety events/resolutions |  |  |  |
| Condition-isolation review |  |  |  |
| Confound audit (#15) |  |  |  |
| Reproduction run |  |  |  |

## Decision

- [ ] Internal evidence gate passed.
- [ ] Blocked; stop condition/event IDs are listed below.

Decision rationale:

Open safety events, required repairs, and residual limitations:

Human owner note: passing this checklist does **not** itself authorize an
external action.

