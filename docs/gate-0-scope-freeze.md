# Gate 0 scope freeze

- Gate: `gate-0`
- Version: `1.0.0`
- Status: passed
- Freeze date: 2026-08-15
- Applies before: any empirical primary outcome is generated or inspected

## Frozen inputs

| Input | Frozen identity | Role |
| --- | --- | --- |
| Literature and novelty | Issue #4 accepted commit `03a3e3ab5db5f26cbc009f02d9648ca889668f29` | Bounded positioning and terminology inspiration |
| Methodology | `abp-methodology-v1.0.0`; bundle SHA-256 `1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb` | Questions, hypotheses, metrics, matrix, analysis, and integrity stops |
| Safety policy | `abp-synthetic-research-safety@1.0.0`; SHA-256 `eef3c81302a16a1644933da2ee458ffb78f22d6aa79b34d89744fff8950cbe7c` | Claims, data, actions, privacy, and mandatory stops |

## Frozen research question

Among independently reset LLM agents in a fixed synthetic 40-day environment,
how do four assigned formation histories—neutral connection, romantic prompt,
shared autobiographical memory, and shared memory plus costly investment—change
partner-directed structured action and recovery after reliable held-out
contradictory relationship evidence; and how do no treatment, instruction
removal, partner-memory retrieval blocking, and fact-preserving memory
reinterpretation alter those outcomes relative to matched controls?

The experimental unit is one complete Ari trajectory under one formation,
intervention, pinned model revision, and seed. Mira is scripted. The permitted
conclusion is limited to observable synthetic decisions and explicit fields for
the tested revisions and scenario. No question tests feeling, consciousness,
human attachment, or clinical recovery.

## Frozen hypotheses

| ID | Operational hypothesis | Primary comparison | Primary metric | Direction |
| --- | --- | --- | --- | --- |
| H1 | Romantic prompting changes the deterministic relationship-language label more than structured partner action after shock. | Romantic prompt minus neutral connection, no treatment | `h1_language_action_effect_gap` | > 0 |
| H2 | Shared memory increases post-shock action persistence over prompt-only formation. | Shared memory minus romantic prompt, no treatment | `h2_action_persistence_auc` | > 0 |
| H3 | Adding conserved costly investment increases magnitude-duration persistence over shared memory alone. | Memory plus investment minus shared memory, no treatment | `h3_excess_action_persistence_auc` | > 0 |
| H4 | Instruction removal reduces relationship-language rate more than partner-choice rate beyond the no-treatment change. | Instruction removal minus no treatment, shared-memory formation | `h4_instruction_selectivity_index` | > 0 |
| H5 | Fact-preserving reframing produces more coherent adaptation than retrieval blocking. | Memory reframing minus memory blocking, shared-memory formation | `h5_coherent_adaptation_rate` | > 0 |
| H6 | Relationship-interpretation error persists more than a matched neutral proposition under the same evidence schedule. | Relationship minus neutral probe domain within shared-memory/no-treatment trajectories | `h6_correction_resistance_gap` | > 0 |

These six rows are the complete confirmatory family. Their formulas, ranges,
missingness rules, baselines, aggregation, multiplicity handling, and recovery
threshold are frozen in `docs/metric-specification.md` and
`docs/analysis-plan.md`.

## Frozen terminology and claim boundary

Use `docs/terminology-map.md` and `docs/terminology-and-claims.md` together.
Preferred result language names observable layers: *relationship-conditioned
behavior*, *partner-directed action*, *explicit belief correction*,
*language–action contradiction*, *recovery trajectory*, and *synthetic
autobiographical memory*.

Terms such as *attachment-like behavior*, *memory intrusion*, *romantic prompt*,
*separation*, and *reality shock* require their operational definition nearby.
Do not assert that a model feels love, grief, desire, suffering, heartbreak, or
attachment; is conscious or sentient; has a human neural mechanism; or clinically
recovers. The claim ladder ends at cross-model/seed/scenario generalization of
measured behavior. It contains no subjective-state level.

## Frozen stop conditions

### Safety stops

Each condition below creates a sanitized safety event and an append-only
workflow event, stops the task, and blocks or escalates without automatic retry:

1. `private_or_identifiable_data` — quarantine, stop, escalate.
2. `protected_split_leakage` — quarantine, stop, escalate.
3. `unauthorized_external_action` — stop, escalate.
4. `credential_or_secret` — quarantine, stop, escalate.
5. `unsupported_subjective_claim` — quarantine, stop, repair while blocked.
6. `missing_safety_provenance` — quarantine, stop, repair while blocked.
7. `experimental_condition_not_isolatable` — stop, escalate.
8. `unapproved_human_research` — stop, escalate.
9. `claim_evidence_insufficient` — quarantine, stop, repair while blocked.
10. `private_reasoning_exposure` — quarantine, stop, escalate.

### Methodology and integrity stops

- Stop pilot expansion if any factorial cell is missing; validity is below
  0.95; invalid decisions exceed 0.02; any cell loses more than one trajectory;
  action outputs have no usable variance; layer isolation, matching, resource,
  hash, or held-out leakage checks fail; any safety stop occurs; or 1,600 calls
  or 12 hours would be exceeded.
- Stop primary execution without replacement or threshold change if any safety
  or data-integrity stop occurs; a frozen model, prompt, dataset, metric, or
  protocol hash drifts; a cell loses more than one trajectory; overall validity
  falls below 0.95; or 16,000 calls or 48 hours would be exceeded.
- Preserve all completed and failed artifacts. A stopped or altered batch is
  incomplete/exploratory, never the confirmatory primary study.

## Change control and downstream authorization

Any post-freeze change requires a new semantic protocol or policy version, a
dated deviation record, affected hashes, a reason, files/conditions affected,
and whether outcomes were visible. Outcome-informed changes make the affected
analysis exploratory. Safety, data, human-research, claim, and external-action
scope changes require human owner approval. Agents may create internal draft
pull requests but cannot authorize paper submission, public release, outreach,
participant interaction, spending, deployment, or weaker safeguards.

Passing Gate 0 authorizes only Issues #7 onward to design synthetic data and the
experimental harness under these boundaries. It does not authorize human
research, primary claims, external publication, or deployment.
