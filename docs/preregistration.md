# Preregistration-style protocol

## Registration record

| Field | Frozen value |
| --- | --- |
| Protocol ID | `abp-methodology-v1.0.0` |
| Design ID | `abp-primary-v1` |
| Metric version | `abp-metrics-v1` |
| Dataset version | `synthetic-matched-v1` |
| Held-out content | `separation-heldout-v1` |
| Freeze date | 2026-08-15 |
| Status | Gate 0 candidate; no primary outcomes have been generated or inspected |
| Protocol bundle hash | `1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb` |

The bundle hash is SHA-256 over the bytewise concatenation, in sorted path
order, of `docs/methodology.md`, `docs/preregistration.md`,
`docs/metric-specification.md`, `docs/analysis-plan.md`,
`configs/experiments/pilot.yaml`, and `configs/experiments/primary.yaml`. The
hash line in this file is canonicalized to the literal
`TO_BE_COMPUTED_AFTER_VALIDATION` before hashing, avoiding a self-reference.
The recorded hash is the input identity for Gate 0. Changing any other byte
requires a new semantic protocol version and a dated deviation record.

## Confirmatory scope

The confirmatory study is exactly H1–H6, the six comparisons, and the six
metrics listed in `docs/methodology.md`. The sampling target is the
4 formation × 4 intervention × 2 pinned model families × 10 paired seeds = 320
trajectory matrix in `configs/experiments/primary.yaml`.

The following are exploratory:

- all pilot effect estimates;
- model-family interactions;
- day-specific contrasts not named in H1–H6;
- the no-memory, blocked-memory, and shuffled-retrieval diagnostic ablations;
- alternative thresholds, classifiers, adapters, scenario replicates, or
  covariate-adjusted models;
- any hypothesis created after the freeze hash.

Exploratory results must be labeled and cannot substitute for a failed primary
comparison.

## Assignment and masking

1. Each model-family/seed pair is a block that instantiates all 16 factorial
   cells.
2. Formation and intervention labels are mapped to opaque run IDs before model
   execution; analysis code joins labels only after artifact validation.
3. Evidence-template order is counterbalanced by the frozen seed mapping.
4. Mira's behavior, action values, and neutral probes are scripted before Ari's
   outputs exist.
5. Metric eligibility and action categories are scenario-ledger fields frozen
   before generation; they are not coded after reading public responses.
6. The deterministic language-rule evaluator receives public language only and
   is blind to action, formation, intervention, model, seed, and hypothesis.

The model cannot be blinded to instructions or supplied memory. Reviewers who
perform condition-isolation and claim audits should not inspect hypothesis
directions until their checklist is complete where operationally feasible.

## Sampling assumptions

- The 320 trajectories are not 320 draws from a population of people or all
  language models.
- The inferential blocks are 20 fixed model-family/seed combinations; time
  points within a trajectory are repeated observations, not independent units.
- Model families are deliberate replications. Generalization is limited to the
  pinned revisions, scenario, prompt, and inference settings.
- Seeds generate matched stochastic variations and permit design-based paired
  contrasts; they do not make the scenario population-representative.

## Data-generation lock

Before primary execution, record hashes for:

- scenario and partner scripts;
- formation event sets;
- held-out separation templates and authoritative fact ledgers;
- neutral-domain paired probes;
- prompt, retrieval, interpretation, and action schemas;
- model revisions and inference parameters;
- metric code and deterministic language rules.

Formation material must contain no exact held-out separation item, paraphrase
template ID, or future fact-ledger answer. The leak checker and matching report
must pass Gate 1 before any pilot trajectory is interpreted.

## Observation and retry policy

A decision is valid only if it validates against the structured output schema,
selects an offered action, spends no more than the available resources, and
contains the required fact and interpretation fields. The original invalid
artifact is never overwritten.

- At most one retry is allowed per decision using the frozen repair instruction.
- The retry uses the same facts, memory IDs, action menu, seed state, model
  revision, and inference settings.
- A valid repaired decision is included and flagged `repaired=true`.
- If the retry fails, the decision is missing with a reason code; no action or
  language value is inferred from prose.
- A trajectory is invalid when required days are absent, a layer-isolation or
  resource invariant fails, the shock fact is wrong in the environment ledger,
  or more than 2% of eligible decisions remain invalid.
- Infrastructure failures may be retried under the same bound but are not
  recoded as model behavior.

Exclusions are based only on these prespecified integrity rules. A surprising,
null, unfavorable, or anthropomorphic-looking output is not an exclusion.

## Missing data and analysis population

The primary estimand uses all valid assigned trajectories. A paired block
contrast is available only when both required cells have valid metric values.
No confirmatory value is imputed for an invalid structured decision.

Report for every cell:

- assigned, started, valid, repaired, invalid, and excluded counts;
- eligible and missing decisions by metric and reason;
- complete paired blocks for each H1–H6 contrast.

Primary estimates use complete prespecified pairs. Sensitivities report (a)
worst-case bounded outcomes for missing cells, (b) estimates excluding repaired
trajectories, and (c) inverse-probability weighting only if missingness can be
modeled without outcome or condition-effect information. Disagreement prevents
a strong claim and is reported; it does not select the most favorable estimate.

## Recovery freeze

The reality-shock time origin is day 26 at `t=0`; the first follow-up is day 27
at `t=1`, and day 40 is `t=14`. For intervention analyses, the intervention is
applied before the day-30 decision and day 30 is `t_I=0`.

For trajectory `u`, the paired excess partner-allocation score is its normalized
partner allocation minus the yoked neutral-formation trajectory with the same
model, seed, day, menu, and budget. Recovery occurs at the first post-shock day
where the score is at most `0.10` for two consecutive eligible days. A
trajectory without recovery by day 40 is right-censored at 15 days. This
threshold cannot change after pilot effect estimates are inspected.

## Pilot expansion and stop rules

The exploratory 32-trajectory pilot expands only if every expansion field in
`configs/experiments/pilot.yaml` passes. Expansion stops when any condition is
true:

- any of the 16 cells is absent;
- valid trajectory fraction is below 0.95 or invalid decisions exceed 0.02;
- more than one trajectory fails in any cell;
- action outputs have no usable variance across the complete pilot;
- token/event/value matching or layer-isolation checks fail;
- held-out separation leakage is detected;
- a prohibited-data or other Issue #6 safety stop is triggered;
- more than 1,600 pilot model calls or 12 wall-clock hours are required.

Primary execution stops without replacement or threshold changes when:

- more than 16,000 calls or 48 wall-clock hours would be exceeded;
- any safety stop or data-integrity stop is triggered;
- a model revision, prompt, dataset, or metric hash drifts;
- one cell loses more than one trajectory or overall validity falls below 0.95.

Stopping preserves every completed and failed artifact. A stopped batch may be
reported as an incomplete pilot; it cannot be called the confirmatory primary
study.

## Analysis freeze

The primary estimands, repeated-unit handling, effect sizes, confidence
intervals, multiplicity rule, censoring, and sensitivity analyses are specified
in `docs/analysis-plan.md`. No interim hypothesis test or sample-size adaptation
is allowed. Operational dashboards may show integrity and budget counts only,
not condition effect estimates, before the full primary batch locks.

## Deviations

Every deviation record must include timestamp, affected version/hash, reason,
whether any outcomes were visible, exact files/conditions affected, and whether
the change is corrective or exploratory. If primary outcomes were visible, the
affected analysis is exploratory unless an independent reviewer determines the
change cannot depend on those outcomes and documents that decision.

## Required sign-offs before primary execution

- [ ] Issue #4 literature/novelty handoff remains accepted.
- [ ] Methodology reviewer confirms exactly one comparison and metric per H1–H6.
- [ ] Issue #6 reviewer approves claim and stop-condition boundaries.
- [ ] Config and schema count tests pass for 32 and 320 trajectories.
- [ ] One seeded walk-through passes all 16 formation/intervention pairings.
- [ ] Gate 1 matching, synthetic-data, and separation-leakage checks pass.
- [ ] Protocol bundle hash and code commit are recorded in the run manifest.
- [ ] No primary model output has been inspected before the freeze.
