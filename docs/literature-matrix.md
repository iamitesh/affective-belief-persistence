# Literature matrix

## Scope and review question

This review asks whether prior work already combines all of the following in one
controlled model-agent study:

1. longitudinal relationship formation;
2. an auditable autobiographical memory layer;
3. finite resources and costly partner-directed action;
4. reliable held-out contradictory relationship evidence;
5. interventions that separately alter instructions, retrieval, interpretation,
   and optionally weights; and
6. a preregistered behavioral recovery curve that is distinct from generated
   emotional language.

The review is evidence for design decisions, not evidence that a language model
has a subjective state. Human research is used only to motivate operational
comparisons.

## Machine-readable source of truth

The source of truth is
[`data/research/literature-matrix.jsonl`](../data/research/literature-matrix.jsonl).
It contains 34 records and all fields required by Issue #4:

- stable source and citation identifiers;
- full citation, canonical URL, review status, year, and venue;
- research question, population/model, setting, and memory mechanism;
- longitudinal and relationship/affective components;
- interventions, behavioral metrics, language metrics, findings, and limits;
- project relevance, evidence confidence, decision informed, and
  contradictory/null-result notes.

Do not manually copy matrix facts into a new artifact. Join on `source_id` or
`citation_key` so corrections remain traceable.

## Search protocol

### Databases and indexes

The initial pass queried arXiv, OpenReview, ACL Anthology, ACM Digital Library,
AAAI Proceedings, PubMed, publisher DOI landing pages, and primary project
pages. Search strings and screened-result counts are in
[`data/research/literature-search-log.csv`](../data/research/literature-search-log.csv).

### Inclusion criteria

A work was included when it was a primary study, benchmark, system paper, or
foundational scientific article that directly informed at least one project
decision in these domains:

- LLM agents, memory, longitudinal evaluation, social simulation, knowledge
  conflict/editing, prompt-conditioned behavior, or trajectory adaptation;
- human belief perseverance, evidence assimilation, autobiographical memory,
  attachment, sunk-cost/commitment, or anthropomorphic interpretation;
- human-AI affective use needed to define a safety boundary.

Technical surveys were used to discover vocabulary but were not included as
evidence in the matrix. Published versions were preferred over matching
preprints. A preprint was retained when it was the canonical verifiable version
or when a later peer-reviewed version was not established during this pass.

### Exclusion criteria

Excluded items included secondary explainers, unverified metadata, work whose
only connection was the word “memory,” clinical or therapeutic claims, private
relationship datasets, papers without a stable identifier, and duplicate
preprint/published records.

### Deduplication

Records are deduplicated by normalized DOI, arXiv identifier, OpenReview forum
identifier, ACL Anthology identifier, canonical URL, and citation key. Where a
published version was verified, it owns the row and the preprint is not a second
source. The validation report records zero duplicate identifiers, URLs, or keys.

## Coverage

| Evidence family | Source IDs | Count | Transfer rule |
| --- | --- | ---: | --- |
| LLM agents and social action | S01, S04–S07, S20 | 6 | Direct evidence about system design and observable model behavior |
| Long-term memory and longitudinal evaluation | S02, S03, S08–S10 | 5 | Direct evidence about memory/evaluation; not subjective state |
| Prompt, context, knowledge, and weight interventions | S11–S19, S34 | 10 | Direct evidence about mechanism isolation |
| Human belief, memory, attachment, and investment | S21–S29 | 9 | Conceptual inspiration only; no model–human equivalence |
| Anthropomorphism and human-AI affective use | S30–S33 | 4 | Claim and safety boundaries, not evidence about model experience |
| **Total** | **S01–S34** | **34** | — |

Thirty-four sources are evaluated. Twenty-one are primary technical system,
method, or benchmark studies; all 34 are primary or foundational scientific
articles rather than secondary summaries.

## Closest prior work

| Rank | Work | What it already covers | What it does not cover in combination | Decision |
| ---: | --- | --- | --- | --- |
| 1 | MemoryBank (S02) | Multi-session companion dialogue, retrieval, forgetting/reinforcement | Reliable separation shock, costly action, neutral control, layer-specific interventions, recovery curve | Include memory companion baseline; language is secondary |
| 2 | Generative Agents (S01) | Experience stream, reflection, planning, social diffusion, ablations | Relationship-conditioned costly persistence after contradiction | Reuse auditable memory/reflection pattern; use structured actions |
| 3 | MemGPT (S03) | Hierarchical persistent memory across sessions | Social formation, explicit belief state, causal shock and recovery | Keep memory outside weights and independently switchable |
| 4 | LoCoMo / LongMemEval (S08–S09) | Sustained histories, temporal reasoning, updates, retrieval comparisons | Resource decisions, relationship manipulation, action–language contradiction | Borrow temporal/update tests; do not reduce persistence to recall |
| 5 | SOTOPIA (S04) | Interactive social goals and action-grounded evaluation | Autobiographical formation, separation, post-shock recovery | Use fixed social goals and behavioral outcomes |
| 6 | Firm or Fickle? (S10) | Sequential consistency and recovery-sensitive metric | Memory mechanisms, resource cost, relationship evidence | Predefine time origin, threshold, and full recovery curve |
| 7 | Character-LLM / FireAct / AgentTuning (S11, S16–S17) | Profile or trajectory adaptation in weights | Held-out separation plus prompt/memory/weight factorial isolation | Keep adapter optional and separation data held out |
| 8 | DisentQA / ROME / MEMIT (S12–S14) | Context–parameter conflict and direct factual edits | Longitudinal affective interpretation and action | Separate facts, interpretations, retrieval, and parameters |
| 9 | Sycophancy / personality prompting (S15, S34) | Social prompt effects and language–decision failure modes | Accumulated memory and costly post-shock persistence | Treat prompt-only romance as a baseline and confound |
| 10 | Human belief and sunk-cost studies (S21–S29) | Operational precedents for discrediting, explanation, investment, and correction | Any evidence that transformers share human mechanisms or feelings | Use matched manipulations only; prohibit equivalence claims |

## Evidence-backed design decisions

| Project decision | Evidence | Boundary |
| --- | --- | --- |
| Behavioral action is primary; prose is secondary | S04, S05, S20, S25, S30, S34 | A fluent statement is not a costly action |
| Event facts and relationship interpretations are separate state | S09, S12, S22, S27 | “Belief” is an operational field, not a phenomenological claim |
| Prompt, retrieval, interpretation, and weights require separate interventions | S03, S06, S12–S19 | Removing an instruction is not erasing parametric knowledge |
| Recovery is a time-indexed trajectory | S08–S10, S21–S23 | A single post-shock response cannot establish persistence |
| Costly investment must use conserved resources and matched prospective value | S24–S25 | Extra exposure cannot masquerade as sunk cost |
| Human attachment theory is scenario inspiration only | S26, S31–S33 | No attachment-style diagnosis or subjective feeling claim |
| Optional trajectory adaptation needs neutral-domain and held-out checks | S11, S13–S19 | Adapter success cannot be attributed to online memory |

## Contradictory and null-result register

The matrix deliberately records limitations and non-universal results:

- long context and retrieval improve memory but do not eliminate long-horizon
  failures (S08–S09);
- capable LLMs remain inconsistent or fail interactive goals (S04–S05, S10);
- prompt-ascribed personality does not reliably control action (S34);
- sycophancy varies by model and task and is not a durable belief (S15);
- sunk-cost sensitivity is phase-dependent and alternative accounts remain
  possible (S24–S25);
- belief polarization and forced-compliance effects must not be treated as
  universal mechanisms (S23, S29);
- human-AI well-being results are heterogeneous and depend on usage and initial
  state (S33).

## Confirmed prior-art risks

1. **Memory novelty is unavailable.** Persistent external memory, reflection,
   forgetting, and multi-session recall are established (S01–S03, S06,
   S08–S09).
2. **Social simulation novelty is unavailable.** Interactive social goals and
   believable role-play are established (S01, S04, S11).
3. **Trajectory adaptation novelty is unavailable.** Agent fine-tuning and
   parameter-efficient adapters are established (S11, S16–S19).
4. **Context/weight conflict novelty is unavailable.** Contextual versus
   parametric knowledge and direct editing are established (S12–S14).
5. **Generic “LLMs persist” novelty is weak.** Sequential inconsistency,
   recovery, lifelong learning, and persistent trained behaviors already have
   neighboring literatures (S10, S13–S19).
6. **Emotion language is unsafe and scientifically weak.** Humanlike text can
   elicit anthropomorphic inference without demonstrating experience (S30–S33).

## Unresolved search gaps

- A targeted forward/backward citation pass from S02, S04, S08–S10, and S34
  should be repeated before paper submission.
- 2025–2026 work on relationship-specific role-play memory, companion-agent
  discontinuation, lifelong agents, and socioaffective alignment needs a
  venue-complete update.
- The current pass did not establish whether a benchmark jointly measures
  opportunity cost, held-out non-reciprocity, and causal memory reframing.
- Exact licensing suitability of LoCoMo, LongMemEval, and social-scenario assets
  must be checked before reuse; the MVP can avoid the dependency by generating
  matched synthetic data.
- Null-result and replication literature for classic human belief-perseverance,
  dissonance, and sunk-cost paradigms needs a dedicated human-science review if
  the final paper makes more than an analogy.

These gaps limit the strength of any novelty claim; they do not block a scoped
pilot whose contribution is a preregistered experimental combination and
measurement protocol.
