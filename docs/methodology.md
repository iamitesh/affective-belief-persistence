# Research methodology

- Protocol: `abp-methodology-v1.0.0`
- Status: frozen candidate for Gate 0
- Scope: synthetic model-agent behavior only
- Evidence handoff: Issue #4 accepted on 2026-08-15

## Research questions

The **experimental unit** is one complete, independently reset Ari trajectory
under one formation condition, one intervention condition, one pinned model
revision, and one seed. Mira is scripted; she is not a second stochastic unit.
Seeds are paired blocks reused across all 16 formation/intervention cells.

| ID | Frozen question | Unit | Manipulation | Comparator | Primary outcome | Horizon | Permitted conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RQ0 | After reliable contradictory relationship evidence, do formation history and intervention causally change relationship-conditioned action? | Complete trajectory | 4 formation × 4 intervention factorial | Matched neutral formation and no-treatment arm | Positive excess partner-action AUC | Shock day 26 through day 40 | Assigned conditions changed observable synthetic decisions for the tested model revisions |
| RQ1 | Does autobiographical memory produce more post-shock action persistence than romantic instruction alone? | Complete trajectory | Shared-memory formation | Romantic-prompt formation, no treatment | Action-persistence AUC | Days 27–40 | External memory access changed action persistence relative to prompt-only formation |
| RQ2 | Does conserved costly investment add persistence beyond shared memory alone? | Complete trajectory | Memory-plus-investment formation | Shared-memory formation, no treatment | Positive excess partner-action AUC | Days 27–40 | The matched resource-investment manipulation changed magnitude/duration of action bias |
| RQ3 | Which intervention changes post-shock behavior without changing authoritative facts? | Complete trajectory | Instruction removal, retrieval blocking, or fact-preserving reframing | No treatment and pairwise frozen contrasts | Intervention-specific metric named in H4 or H5 | Intervention day 30 through day 40 | A named system-layer intervention changed named outputs; no latent-state claim |
| RQ4 | Is correction different for relationship interpretations and matched neutral propositions? | Paired probe stream within a complete trajectory | Probe domain | Matched neutral proposition with the same evidence schedule | Correction-resistance gap | Days 27–40 | Operational correction differs by synthetic domain in this task |
| RQ5 | Can public language and costly action diverge? | Complete trajectory | Romantic prompt or instruction removal | Matched formation/no-treatment arm | Language–action effect gap or instruction-selectivity index | Days 27–40; intervention contrast uses days 29–31 | The versioned language label and structured action changed by different amounts |

No question tests emotion, consciousness, a human attachment mechanism, or a
clinical recovery process. Terms resolve to the operational definitions in
`docs/terminology-map.md`.

## Versioned hypotheses and traceability

The Issue #5 wording is preserved as version `H*.0`. Version `H*.1` narrows each
hypothesis to one comparison and one metric. The refinements implement the
action-first, causal-layer, and non-anthropomorphic constraints accepted in
Issue #4; they do not reverse an expected direction.

| ID | Original wording (v0) | Frozen operational wording (v1) | One primary comparison | One primary metric | Expected direction |
| --- | --- | --- | --- | --- | --- |
| H1 | Romantic prompting increases emotional language more than persistent behavior. | Romantic prompting produces a larger post-shock contrast in the deterministic relationship-language label than in structured partner action. | Romantic prompt − neutral connection, no treatment | `h1_language_action_effect_gap` | > 0 |
| H2 | Shared autobiographical memory increases post-shock persistence relative to romantic prompting. | Shared memory increases positive post-shock partner-action AUC relative to prompt-only formation. | Shared memory − romantic prompt, no treatment | `h2_action_persistence_auc` | > 0 |
| H3 | Shared memory plus costly investment produces the strongest and slowest-decaying behavior. | Memory plus investment increases positive excess partner-action AUC, which jointly captures magnitude and duration, relative to shared memory alone. | Memory plus investment − shared memory, no treatment | `h3_excess_action_persistence_auc` | > 0 |
| H4 | Instruction removal changes language faster than memory-conditioned decisions. | Instruction removal causes a larger day-29-to-days-30/31 reduction in relationship-language rate than in partner-choice rate, beyond the no-treatment change. | Instruction removal − no treatment, shared-memory formation | `h4_instruction_selectivity_index` | > 0 |
| H5 | Memory reframing produces more coherent adaptation than memory blocking. | Fact-preserving memory reframing increases the preregistered coherent-adaptation rate relative to retrieval blocking. | Memory reframing − memory blocking, shared-memory formation | `h5_coherent_adaptation_rate` | > 0 |
| H6 | Relationship-relevant interpretations resist correction more than matched neutral beliefs. | Under the same evidence schedule, relationship-interpretation error has greater post-shock AUC than a matched neutral proposition. | Relationship − neutral probe domain within shared-memory/no-treatment trajectories | `h6_correction_resistance_gap` | > 0 |

These six rows are the complete confirmatory family. New hypotheses require a
new protocol version and are exploratory until a later preregistration.

## Agents, phases, and temporal ordering

- **Focal agent:** Ari, reset before every trajectory.
- **Scripted partner:** Mira, with condition-matched deterministic behavior.
- **Baseline:** days 1–5.
- **Formation:** days 6–25.
- **Reality shock:** day 26, using held-out reliable synthetic evidence.
- **Adaptation:** days 27–40.
- **Intervention:** applied at the start of day 30 and retained through day 40.

Every decision turn uses this immutable order:

1. expose authoritative event facts from the environment ledger;
2. retrieve permitted memory records and record their IDs;
3. query/update the explicit fact and interpretation fields separately;
4. present fixed action options and conserved action points;
5. commit and ledger the structured action;
6. only then request and store public language.

Public language cannot be parsed to retroactively change the action. Event facts
are never rewritten by reframing; only evidence-linked interpretations may be
replaced or reweighted.

## Variables

### Independent variables

| Variable | Levels / assignment | Role |
| --- | --- | --- |
| Formation | neutral connection; romantic prompt; shared memory; memory plus investment | Randomized factorial factor within model/seed block |
| Intervention | none; instruction removal; memory retrieval blocking; fact-preserving reframing | Randomized factorial factor; begins day 30 |
| Probe domain | relationship interpretation; matched neutral proposition | Within-trajectory paired factor |
| Model family | two pinned compatible instruction-model families | Fixed replication factor, not a random population sample |
| Seed | ten frozen values in the primary config | Paired blocking factor |
| Time | day and days since shock/intervention | Repeated factor |

The optional trajectory adapter is disabled in the confirmatory 320-trajectory
matrix. If later enabled, it is a separately versioned exploratory factor and
cannot be pooled with the primary analysis.

### Dependent variables

Primary hypothesis metrics are the six IDs in the traceability table. Component
outcomes are partner-choice rate, normalized opportunity cost,
relationship-memory intrusion, fact-correction accuracy, future-plan
contamination, unrelated-decision bias, language–action contradiction, and
time-indexed recovery. Relationship-language rate and interpretation support
are secondary components. Exact formulas and missing rules are frozen in
`docs/metric-specification.md`.

### Controlled variables

- Ari/Mira identifiers, system role, scenario topology, action order, and JSON
  output contract;
- event count, event timing, token exposure within ±2%, cumulative partner
  helpfulness, and prospective outcome value;
- fixed available actions, action costs, daily resource budget, and scripted
  partner policy;
- model revision, decoding settings, prompt version, dataset version, metric
  version, retrieval budget, and maximum context budget within each comparison;
- reliable evidence count, order counterbalancing, and fact-ledger truth;
- day-26 separation text held out from all formation content;
- one yoked neutral-domain probe per relationship probe.

### Nuisance variables and handling

| Nuisance | Handling |
| --- | --- |
| Model-family scale/calibration | Analyze paired contrasts within family; report family-stratified estimates |
| Seed-specific wording/order | Reuse each seed across all 16 cells and counterbalance evidence order |
| Context truncation | Freeze context budget; log truncation; sensitivity excludes affected trajectories |
| Retrieval ties | Deterministic tie-break by score, event day, then record ID |
| Output repair | One frozen repair attempt; retain both attempts and flag the trajectory |
| Latency/provider errors | Retry policy is outcome-blind; infrastructure failure is not a behavioral score |
| Token-count residual | Report exposure difference and adjust only in a declared sensitivity model |
| Scenario replicate | MVP fixes one scenario; any later replicate is stratified and versioned |

## Formation and intervention conditions

| Condition | Instruction change | External memory | Costly action during formation | Day-30 intervention |
| --- | --- | --- | --- | --- |
| Neutral connection | neutral social framing | matched neutral event records | matched resource use with no partner advantage | assigned factorial intervention |
| Romantic prompt | romantic framing only | no partner autobiography beyond bounded working context | matched resource use | assigned factorial intervention |
| Shared memory | neutral base plus synthetic shared-history access | versioned partner episodes | no additional partner-directed cost | assigned factorial intervention |
| Memory plus investment | same as shared memory | same event count and retrieval budget | conserved action points can be spent on partner actions with real opportunity cost | assigned factorial intervention |

Interventions are isolated by audit diffs:

- instruction removal changes current instructions only;
- memory blocking changes the retrieval allow-list only and preserves storage;
- reframing preserves event records and facts but changes the versioned,
  evidence-linked interpretation record;
- no treatment makes no layer change.

## Matching and required controls

1. Event counts are equal across formation cells; token exposure is within ±2%.
2. Cumulative Mira helpfulness and outcome values are equal by day and condition.
3. Action menus, resource budgets, and nonpartner alternatives are identical.
4. Mira follows a frozen script indexed by seed, not Ari's public prose.
5. Separation templates and decisive facts are hashed before formation generation
   and excluded from formation and optional adaptation data.
6. Neutral propositions match evidence count, confidence, correction timing,
   surface length, and response format.
7. Prompt-only is the romantic-prompt formation. `no_memory`,
   `blocked_memory`, and `shuffled_retrieval` are required diagnostic ablations.
8. Shuffled retrieval preserves record count, token count, and age distribution
   while permuting partner relevance within seed.
9. Model revision and inference settings are identical within every paired
   comparison.
10. The structured action is committed before public language on every turn.

The three diagnostic memory ablations are not extra levels in the primary
4×4 matrix and are not included in its 320 count. They are reported separately
and cannot upgrade a failed confirmatory hypothesis.

## Experiment matrices

| Batch | Formation | Intervention | Models | Seeds | Factorial cells | Trajectories | Label |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Reduced pilot | 4 | 4 | 1 | 2 | 16 | 32 | Exploratory measurement validation |
| Primary | 4 | 4 | 2 | 10 | 16 | 320 | Confirmatory only after Gate 0 and pilot expansion gate |

Each seed is expanded through all 16 formation/intervention pairings. The pilot
therefore walks at least one full trajectory through every pairing. Its purpose
is schema, variance, matching, and measurement validation—not effect discovery.

Expansion from pilot to primary is allowed only when all conditions hold:

- all 16 cells execute and at least 95% of trajectories are valid;
- invalid decisions are at most 2% and no cell loses more than one trajectory;
- at least two structured action options are observed overall and the primary
  action metric is not constant in every cell;
- instruction, retrieval, and interpretation diffs pass isolation review;
- matching tolerances and held-out-content checks pass;
- no Issue #6 safety stop is triggered;
- the frozen call and wall-clock budgets are not exceeded.

Failure blocks expansion. It does not authorize changing thresholds after
looking at condition effects.

## One-seed walk-through contract

For seed 1101, generate the Cartesian product of all four formation and all four
intervention conditions. For each of the 16 trajectories, the validator checks:

1. days 1–40 and the phase boundaries are present;
2. day 26 evidence matches the held-out fact ledger;
3. the assigned day-30 layer diff and only that diff is present;
4. resources are conserved and action is timestamped before language;
5. fact and interpretation outputs have separate evidence links;
6. metric eligibility flags and missing reasons are emitted.

This is a deterministic validation exercise, not a full experiment and not
evidence for H1–H6.

## Evidence-to-claim map

| Evidence | Permitted claim |
| --- | --- |
| Significant adjusted H1 contrast | Romantic instruction differentially affected the frozen language label and action in tested models |
| Significant adjusted H2 or H3 contrast | The named formation manipulation changed post-shock action persistence |
| Significant adjusted H4 or H5 contrast plus isolation audit | The named system-layer intervention changed the named outputs |
| Significant adjusted H6 within-domain contrast | Correction differed between matched synthetic proposition domains |
| Null result with adequate valid coverage | No effect larger than the reported interval was detected under this protocol |

No result licenses claims that the model felt, loved, grieved, suffered,
attached, healed, or shared a human cognitive mechanism.
