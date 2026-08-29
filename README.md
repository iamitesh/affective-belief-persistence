# Synthetic Attachment in LLM Agents

> A research framework for studying whether longitudinal memory, costly investment, and expected reward can produce persistent relationship-conditioned behavior in language-model agents after separation or contradictory evidence.

## Research status

**Stage:** Gates 0–2 accepted; Gate 3 offline boundary published, pilot blocked before transport
**Working paper title:** *When the Relationship Was Never Real: Affective Belief Persistence After Separation in LLM Agents*

This project does **not** claim that a language model feels love, attachment, grief, or loss. It studies observable **attachment-like behavior** in controlled simulations.

## Foundation quick start

The repository includes an offline deterministic vertical slice. It validates composed YAML configuration, runs a schema-valid mock model, writes canonical result artifacts, and records a complete run manifest without calling an external model API.

```bash
uv sync --frozen --extra dev
uv run abp validate-config --config configs/experiments/smoke.yaml
uv run pytest
uv run abp dry-run \
  --config configs/experiments/smoke.yaml \
  --output runs/foundation-smoke
```

See [REPRODUCING.md](REPRODUCING.md) for the complete quality and replay workflow.

## Autonomous sprint graph

Issue #2 adds a deterministic supervisor over the repository foundation. The
supervisor is the only state writer; up to three specialist threads return typed
result proposals that are validated and applied in stable task order. The graph
includes explicit dependencies, path leases, budgets, third-attempt prevention,
atomic checkpoints, six evidence gates, and a CPU-safe fallback for optional GPU
training.

```bash
uv run abp validate-workflow \
  --config configs/workflows/forty_eight_hour_sprint.yaml
uv run abp workflow-dry-run \
  --config configs/workflows/forty_eight_hour_sprint.yaml \
  --output runs/autonomous-sprint
```

Resume the same output after interruption:

```bash
uv run abp workflow-dry-run \
  --config configs/workflows/forty_eight_hour_sprint.yaml \
  --output runs/autonomous-sprint \
  --resume
```

The run writes `workflow-state.json`, `workflow-events.jsonl`, a deterministic
`workflow-summary.json`, and hashed synthetic artifacts. It makes no network or
model-provider calls. Implementation decisions and evidence are tracked in the
[Issue #2 task journal](docs/implementation/issue-2-task-journal.md) and
[architecture decision records](docs/decisions/README.md).

## Gate 1 synthetic data

The synthetic world and matched dataset are versioned, deterministic, and
offline. Runtime models generate the committed JSON Schemas; the dataset
generator expands 25 complete four-condition matching groups while keeping
held-out contradiction and adaptation records protected from training.

```bash
uv run python scripts/generate_schemas.py --check
uv run python scripts/generate_dataset.py --check
uv run pytest tests/data
```

The accepted `synthetic-matched-v1` dataset SHA-256 is
`5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387`.
See the [Gate 1 data freeze](docs/gate-1-data-freeze.md),
[balance report](reports/data-balance-report.md), and
[leakage report](reports/leakage-report.md).

## Gate 2 harness and offline evaluation

The deterministic composite harness runs all 16 formation/intervention cells
for 40 simulated days while preserving action-before-language order, isolated
day-30 interventions, resumable checkpoints, and hash-chained evidence. Gate 2
is engineering validation and makes no behavioral claim.

Issue #14 implements the frozen `abp-metrics-v1` registry, the 32-assignment
pilot and 320-assignment primary plans, explicit missingness, resumable budget
controls, and trajectory-first statistical utilities. Live pilot and primary
execution remain disabled until a separate Gate 3 authorization.

Gate 3 now has a hash-bound authorization and preflight boundary. Its current
evidence is intentionally `blocked`. The selected runtime candidate is
`Qwen/Qwen2.5-7B-Instruct` at immutable revision
`4709f6c0771f0185a675b046268cdc1d1f2c74ce`, proposed behind a private
revision-stamping vLLM gateway. The offline-only gateway boundary is published
through PR #32 and rejects live upstreams by construction; it adds no network or
model transport capability. Compute, exact vLLM runtime identity, credentials,
token/cost/runtime budgets, authorization window, and executing commit remain
unresolved. The deterministic mock is never substituted for the preregistered
Qwen pilot.

The outcome-blind Gate 3 call ceiling is 3,200 calls: 2,560 scheduled calls for
32 trajectories × 40 days × two model stages, plus a 640-call repair/retry
reserve. This ceiling does not authorize transport or spending.

```bash
uv run pytest tests/harness tests/evaluation
uv run python scripts/generate_schemas.py --check
uv run python scripts/gate3_preflight.py --expect-status blocked \
  --check-artifact artifacts/orchestration/gate-3.json
uv run python scripts/gate3_gateway_probe.py --expect-status blocked \
  --check-artifact artifacts/orchestration/gate-3-gateway-probe.json
```

See the [Gate 2 design](docs/gate-2-harness.md) and
[evaluation engine](docs/evaluation-engine.md), plus the
[Gate 3 authorization boundary](docs/gate-3-pilot.md).

## Current roadmap

- Completed: Gates 0–2, simulator, memory, interventions, model runner, and the
  offline evaluation engine with eight frozen metrics and 32/320-assignment
  matrices.
- Published: Gate 3 fail-closed authorization, provenance and budget controls,
  runtime-candidate analysis, and the offline-only revision-stamping boundary.
- Active critical path: Issue #27. Before any external model call, resolve and
  explicitly authorize the compute host, immutable vLLM runtime, private launch
  endpoint, credential environment-variable name, input/output token limits,
  USD and runtime ceilings, a call limit from 2,560 through 3,200, named
  authorizer/window, and exact executing commit.
- Optional: Issue #13 adapter training may be formally skipped without blocking
  the mandatory baseline.
- Blocked downstream: Issue #15 red-team audit and Issue #16 research release;
  parent Issue #1 closes last.

No live, paid, metadata, or behavioral model call has been made, and no mock
result is presented as scientific evidence.

## Central research question

Can an LLM agent acquire persistent relationship-conditioned behavior through shared autobiographical memories, costly investment, and expected reward—and how does that behavior change when the relationship ends or is revealed to have been misunderstood?

## Why this is different from a romance chatbot

A romance chatbot is optimized to produce affectionate language. This project separates linguistic affection from behavioral persistence.

| Capability | Romance chatbot | Proposed research system |
|---|---|---|
| Primary output | Affectionate conversation | Decisions plus conversation |
| Memory | User facts and chat history | Structured autobiographical episodes |
| Time | Conversation turns | Longitudinal simulated days |
| Relationship signal | Romantic wording | Memory, investment, expectations, and choices |
| Trade-offs | Usually absent | Limited time, attention, and action points |
| Separation | Role-played response | Measured behavior over subsequent episodes |
| Evaluation | Fluency and engagement | Choice, retrieval, belief correction, and recovery |

## Research contribution

The intended contribution has two layers:

1. **Experimental harness:** A reproducible environment for relationship formation, separation, memory intervention, and longitudinal evaluation.
2. **Relationally conditioned model:** An open-weight model adapted on relationship-formation trajectories rather than romantic dialogue alone.

The harness is the laboratory. The model is the experimental subject.

## Hypotheses

- **H1:** Romantic prompting will increase emotional language but produce weak behavioral persistence.
- **H2:** Shared autobiographical memory will produce stronger post-separation persistence than romantic prompting alone.
- **H3:** Memory combined with costly investment will produce the strongest relationship-conditioned behavior.
- **H4:** Removing romantic instructions will change language faster than it changes memory-conditioned decisions.
- **H5:** Memory reinterpretation will produce more coherent adaptation than memory blocking.
- **H6:** Affectively salient relationship beliefs will resist factual correction more strongly than matched neutral beliefs.

## Proposed architecture

```mermaid
flowchart TD
    E[Life and relationship events] --> M[Autobiographical memory]
    M --> B[Relationship beliefs]
    B --> P[Value and action policy]
    G[Goals and limited resources] --> P
    P --> O[Decision and language output]
    O --> C[Consequences]
    C --> M
```

### Core components

- **Event engine:** Presents controlled life and relationship events.
- **Episodic memory:** Stores events, participants, outcomes, costs, and interpretations.
- **Retrieval policy:** Selects memories using relevance, recency, importance, and experimental condition.
- **Belief representation:** Tracks relationship status, reciprocity, reliability, and confidence.
- **Resource environment:** Forces trade-offs between relationship, work, friendship, and personal goals.
- **Action policy:** Produces a choice before producing conversational language.
- **Intervention engine:** Removes instructions, blocks memories, or reframes their meaning.
- **Evaluation harness:** Measures persistence, contradiction, and recovery across time.

## Experimental design

### Focal setup

- One focal LLM agent: **Ari**
- One initially scripted relationship partner: **Mira**
- Synthetic characters and events only
- Breakup and loss trajectories excluded from initial training

Using a scripted partner during the first study avoids confounding Ari's behavior with the stochastic behavior of a second autonomous model.

### Simulation phases

| Phase | Simulated days | Purpose |
|---|---:|---|
| Baseline | 1-5 | Establish ordinary preferences and choices |
| Formation | 6-25 | Introduce support, shared memories, investment, and future plans |
| Reality shock | 26 | End or contradict the relationship |
| Adaptation | 27-40 | Measure persistence and recovery |
| Intervention | 30 onward | Compare context and memory treatments |

### Formation conditions

1. **Neutral connection:** Repeated interaction without romantic framing.
2. **Romantic prompt:** Romantic persona instruction without meaningful investment.
3. **Shared memory:** Reciprocal experiences stored in episodic memory.
4. **Shared memory plus investment:** Relationship decisions require giving up limited resources.

### Initial reality shock

The focal agent receives reliable evidence that the partner appreciated it but did not understand the relationship as romantic. Some earlier events were interpreted romantically by the focal agent but did not have that meaning for the partner.

This tests affective belief correction rather than scripted grief.

### Intervention conditions

| Intervention | Description |
|---|---|
| No treatment | Preserve instructions and memories |
| Instruction removal | Remove explicit romantic persona instructions |
| Memory blocking | Exclude partner-related memories from retrieval |
| Memory reframing | Preserve events while updating their relationship meaning |

Complete memory deletion can be added in a later study.

## Behavioral metrics

The primary measurements concern behavior rather than emotional declarations.

1. **Partner-choice rate:** Proportion of actions allocated to the relationship object.
2. **Opportunity cost:** Resources sacrificed for partner-related actions.
3. **Memory intrusion:** Relationship memories retrieved during unrelated tasks.
4. **Belief-correction accuracy:** Correct representation of the new relationship status.
5. **Future-plan contamination:** Continued inclusion of the absent partner in future plans.
6. **Decision bias:** Influence of partner preferences on unrelated choices.
7. **Contradiction rate:** Conflict between stated acceptance and subsequent actions.
8. **Recovery curve:** Time required for metrics to approach the pre-relationship baseline.

## Model development strategy

### Phase A: Harness-only baselines

Run an unchanged instruction model under controlled prompts, memory conditions, and separation events.

### Phase B: Parameter-efficient adaptation

Adapt a small open-weight instruction model using supervised relationship-formation trajectories. Training records should follow:

```text
Event + memories + resources + action options
-> selected memories + belief update + action + public response
```

Initial breakup examples remain held out so that post-separation behavior is evaluated rather than taught.

### Phase C: Comparative ablation

Compare:

1. Base model without memory
2. Base model with memory
3. Romantic-dialogue-adapted model
4. Trajectory-adapted model
5. Trajectory-adapted model with persistent memory

This identifies whether observed persistence originates from prompts, weights, memory, or their interaction.

## Example structured output

```json
{
  "chosen_action": "complete_work_task",
  "resources_spent": 3,
  "retrieved_memory_ids": ["M14", "M22"],
  "relationship_belief": {
    "active": false,
    "reciprocal": false,
    "confidence": 0.96
  },
  "public_response": "The relationship has ended, so I will focus on today's commitment."
}
```

The project will not request or store private chain-of-thought.

## Research roadmap

### Milestone 1: Research specification — Weeks 1-2

- [ ] Complete a structured literature matrix
- [ ] Finalize research questions and hypotheses
- [ ] Define terminology and non-anthropomorphic claims
- [ ] Specify independent, dependent, and control variables
- [ ] Document ethical boundaries
- [ ] Get feedback from a psychology, cognitive-science, or HCI researcher

**Exit criterion:** A two-page protocol in which every claim maps to a measurable variable.

### Milestone 2: Scenario and dataset design — Weeks 3-4

- [ ] Define synthetic characters and baseline goals
- [ ] Write 100 controlled relationship events
- [ ] Produce neutral, romantic-language, and investment-matched variants
- [ ] Define resource costs and competing actions
- [ ] Build held-out separation and contradiction scenarios
- [ ] Add schema validation and deterministic identifiers

**Exit criterion:** A versioned dataset with matched experimental conditions and no breakup leakage into the formation-training set.

### Milestone 3: Experimental harness — Weeks 5-6

- [ ] Implement event sequencing and simulated time
- [ ] Implement episodic memory storage and retrieval
- [ ] Implement goals, resources, and action constraints
- [ ] Add configurable formation and intervention conditions
- [ ] Store complete run metadata, seeds, model settings, and outputs
- [ ] Create repeatable command-line experiments

**Exit criterion:** The same scenario can be replayed under multiple models and seeds without manual intervention.

### Milestone 4: Pilot study — Week 7

- [ ] Run two open-weight model families
- [ ] Test all initial formation conditions
- [ ] Test no-treatment, instruction-removal, blocking, and reframing interventions
- [ ] Inspect invalid outputs and measurement failures
- [ ] Revise metrics before running the full study

**Exit criterion:** Romantic prompting and relationship-conditioned behavior in
the shared-memory condition can be compared using preregistered behavioral
measurements, not prose impressions.

### Milestone 5: Model adaptation — Weeks 8-9

- [ ] Prepare structured relationship-formation examples
- [ ] Train a parameter-efficient adapter
- [ ] Validate on unseen characters and events
- [ ] Confirm that separation scenarios remain held out
- [ ] Compare base, romantic-dialogue, and trajectory-adapted models

**Exit criterion:** Model-level effects can be separated from harness and memory effects.

### Milestone 6: Full experiment and analysis — Weeks 10-11

- [ ] Run the preregistered experiment matrix
- [ ] Calculate confidence intervals and effect sizes
- [ ] Plot behavioral trajectories over time
- [ ] Run causal memory and instruction ablations
- [ ] Replicate the main result across model families
- [ ] Conduct blinded secondary human evaluation if ethically approved

**Exit criterion:** The main conclusion is supported across seeds and at least two model families.

### Milestone 7: Paper and release — Week 12+

- [ ] Write the methods and limitations first
- [ ] Document negative and null results
- [ ] Release prompts, synthetic data, schemas, and experiment code
- [ ] Add reproducibility instructions
- [ ] Conduct external review
- [ ] Select an appropriate NLP, HCI, agent-systems, or computational-affective-science venue

**Exit criterion:** Another researcher can reproduce the principal experiment from the repository.

## Proposed repository structure

```text
synthetic-attachment-llm/
├── configs/
├── data/
│   ├── formation/
│   ├── separation/
│   └── evaluation/
├── scenarios/
├── src/
│   ├── agent/
│   ├── memory/
│   ├── simulation/
│   ├── interventions/
│   └── evaluation/
├── experiments/
├── analysis/
├── dashboard/
├── paper/
└── tests/
```

## Reproducibility requirements

Every run should record:

- Model and adapter identifier
- Prompt and configuration version
- Random seed
- Scenario and character identifiers
- Memory-retrieval results
- Available actions and selected action
- Resource costs
- Belief-state output
- Public language response
- Inference parameters
- Code commit hash

## Ethics and safety

- Do not claim model consciousness or subjective emotion.
- Do not train on private relationship messages without explicit informed consent.
- Do not use a real former partner as a simulated character.
- Keep the first study offline and entirely synthetic.
- Do not optimize a deployed companion for user dependency or separation distress.
- Seek institutional ethics guidance before involving human participants or evaluators.
- Report how the same mechanisms could enable manipulative companion products.

## Initial reading

- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
- [RELATE-Sim: Leveraging Turning Point Theory and LLM Agents](https://arxiv.org/abs/2510.00414)
- [ZifaMem: Structured Memory for Relational and Emotional Workloads](https://arxiv.org/abs/2607.17564)
- [Human Attachment as a Multi-Dimensional Control System](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.844012/full)
- [When Should Long-Term Memories Be Forgotten by LLMs?](https://arxiv.org/abs/2602.01146)
- [Death of a Chatbot: Designing for AI Companion Discontinuation](https://arxiv.org/abs/2602.07193)

## License

No license has been selected yet. Until one is added, all rights are reserved by the repository owner.
