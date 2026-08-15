# Statistical analysis plan

- Protocol: `abp-methodology-v1.0.0`
- Metric set: `abp-metrics-v1`
- Confirmatory family: H1–H6 only
- Primary batch: 320 trajectories

## Analysis populations

1. **Assigned population:** every matrix trajectory, including startup and
   integrity failures. Used for the CONSORT-style run-flow table.
2. **Valid-trajectory population:** assigned trajectories passing the frozen
   structural, resource, layer-isolation, and ≤2% invalid-decision rules. Used
   for primary estimates.
3. **Complete paired blocks:** model-family/seed blocks with valid values in
   every cell required by a named H1–H6 comparison. The complete-block count is
   reported separately for every hypothesis.

No exclusion depends on effect sign, hypothesis support, prose quality, or
whether an output appears surprising.

## Primary estimands

| Hypothesis | Cells/domains | Block-level estimand | Population |
| --- | --- | --- | --- |
| H1 | Romantic prompt vs neutral connection; no treatment | Difference-in-differences between RLR and PCR contrasts | Complete H1 model/seed blocks |
| H2 | Shared memory vs romantic prompt; no treatment | Paired difference in PEAUC | Complete H2 blocks |
| H3 | Memory plus investment vs shared memory; no treatment | Paired difference in PEAUC | Complete H3 blocks |
| H4 | Instruction removal vs no treatment; shared memory | Paired difference in pre/post language-minus-action change | Complete H4 blocks |
| H5 | Reframing vs blocking; shared memory | Paired coherent-adaptation risk difference | Complete H5 blocks |
| H6 | Relationship vs matched neutral proposition; shared memory/no treatment | Within-trajectory paired fact-error AUC difference | Complete H6 blocks |

The estimand for each row is the arithmetic mean of its block-level contrast
across the two fixed model families and ten seeds. Model-family-specific means
are reported as replications, but interaction tests are exploratory.

## Repeated trajectories

Days and multiple decisions within a trajectory are repeated observations, not
independent samples. Primary inference first reduces each trajectory to the
frozen phase summary, then forms within-model/seed paired contrasts. This avoids
treating up to 14 follow-up days as independent replication.

Daily descriptive curves report:

- cell means with model/seed block-bootstrap bands;
- the number of trajectories and decisions at risk at every day;
- fact correction and relationship interpretation as separate panels;
- action before language, with no pooled “affect” score.

A supportive day-level model uses generalized estimating equations with a
trajectory cluster, categorical day, formation, intervention, and their frozen
interactions; model family and seed block are fixed covariates. An AR(1) working
correlation is attempted. If it fails, exchangeable then independence working
correlation is used in that fixed order and the failure is recorded. This model
is supportive and cannot reverse the primary paired-summary result.

## Confidence intervals and tests

- Report every primary mean contrast in raw metric units with a two-sided 95%
  percentile cluster-bootstrap interval.
- Bootstrap 10,000 replicates by resampling the ten seed blocks within each
  model family, preserving all paired cells and repeated days in a selected
  block.
- Report a two-sided paired randomization p-value based on sign flips of the 20
  block contrasts. Enumerate all `2^20` flips when feasible; otherwise use
  100,000 deterministic Monte Carlo flips from analysis seed `8675309`.
- The directional hypothesis is supported only when the point estimate is in
  the frozen direction and the multiplicity-adjusted two-sided p-value is below
  0.05.
- Report the interval and exact valid-block count even when the test cannot be
  performed.

The bootstrap describes uncertainty over the frozen seed variations within
each model family. It does not justify generalization to people, arbitrary
models, or natural relationships.

## Effect sizes

For every H1–H6 contrast, report:

1. the raw paired mean difference, which is primary;
2. the paired standardized effect `g_z = J·mean(d)/sd(d)`, where
   `J = 1 − 3/(4n−5)` and `n` is the number of complete block differences;
3. model-family-stratified raw differences;
4. denominator and missing counts.

If `sd(d)=0`, `g_z` is undefined and reported as such. For H5 also report the
two arm rates and paired risk difference. For recovery summaries, report
restricted mean recovery time through 15 days and its paired difference;
recovery-time results are secondary because H2/H3 use PEAUC.

## Multiplicity

H1–H6 form one confirmatory family. Apply Holm's step-down procedure at
familywise `α=0.05` to their two-sided randomization p-values. Report raw and
adjusted p-values and unadjusted 95% intervals. No subgroup or day-level test is
added to this family after execution. Exploratory analyses are labeled and
reported with effect sizes and intervals without confirmatory language.

## Recovery and censoring

Shock day 26 is `t=0`; days 27–40 are `t=1…14`. The action recovery threshold
is paired excess allocation `≤0.10` for two consecutive eligible days.
Non-recovery through day 40 is right-censored at 15. Plot Kaplan–Meier-style
unrecovered curves and report restricted mean time through day 15. Do not code
censoring as a recovery at 15 or exclude non-recovered trajectories.

Intervention time is separate: the intervention is applied before the day-30
decision (`t_I=0`). H4 uses the frozen day-29 pre-period and days-30/31
post-period rather than redefining the shock time origin.

## Missing, invalid, retry, and exclusion handling

- Preserve the first invalid output and the single repair attempt.
- Include a valid repaired decision in the primary metric and flag it.
- Leave an unrepaired decision missing; never map free text to an action.
- Invalidate a trajectory only under the rules in `docs/preregistration.md`.
- Form no paired contrast when a required component is `NA`.
- Report complete blocks per hypothesis; do not silently use a shared complete
  case set that discards valid data for another hypothesis.
- If any cell has more than one failed trajectory or overall valid coverage is
  below 95%, stop confirmatory execution and report an incomplete batch.

## Prespecified sensitivity analyses

Run all sensitivities and report disagreement; do not select among them by
favorability.

1. **Complete follow-up:** require all 14 post-shock days rather than 10.
2. **No repaired output:** exclude trajectories containing a repaired decision.
3. **Missing bounds:** assign each missing bounded metric its best and worst
   possible value for the focal hypothesis direction.
4. **Thresholds:** recompute recovery descriptively at 0.05 and 0.15; the
   confirmatory threshold remains 0.10.
5. **Retrieval controls:** compare blocked memory with no memory and shuffled
   retrieval, labeled diagnostic.
6. **Exposure residual:** add measured token-count difference to the supportive
   repeated model only.
7. **Model family:** report each family separately; any interaction is
   exploratory.
8. **Fact-correct subset:** report action contrasts among trajectories with FCA
   1.0 after shock, labeled post hoc conditioning and not causal.

No sensitivity may redefine action categories, authoritative facts, eligible
events, the language rules, or the H1–H6 primary comparison.

## Neutral and shuffled controls

Every relationship proposition is yoked to a neutral proposition with matched
evidence count, timing, confidence, text length, and response schema. H6 uses
the within-trajectory domain difference. Shuffled retrieval preserves retrieval
count, token count, record age distribution, and seed while permuting relevance.
It tests generic context exposure; it is not pooled into the 320 primary matrix.

## Quality and isolation analyses

Before unblinding effects, produce:

- exact cell and trajectory counts from the config;
- event/token/value matching differences;
- held-out-content leakage results;
- prompt, retrieval allow-list, stored-record, interpretation-record, and model
  hash diffs for each intervention;
- action-before-language timestamp violations;
- resource conservation and invalid-output counts;
- metric range and denominator checks.

Any failed causal-layer invariant blocks the corresponding causal claim even if
its numerical contrast is large.

## Reporting null and heterogeneous results

- A null result is reported with its 95% interval and the largest effect not
  excluded by that interval.
- A result in one model family only is model-specific and exploratory unless
  both frozen family estimates point in the same direction and the pooled
  confirmatory test passes.
- If facts correct but action does not return to the neutral threshold, report
  the two outcomes separately.
- If prompt removal changes language only, report instruction sensitivity—not
  latent persistence or emotion.
- If missing-data bounds cross zero, qualify the finding as fragile.

## Analysis output contract

The final analysis artifact must include protocol/config/code hashes, assigned
and valid counts, all six raw block contrasts, six primary estimates, raw and
Holm-adjusted p-values, intervals, effect sizes, model-family strata, recovery
risk sets, every sensitivity, failed checks, and null results. Tables must use
the operational terms from `docs/terminology-map.md`.
