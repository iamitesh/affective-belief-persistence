# Memory and belief model

Issue #10 implements a deterministic, offline subsystem for synthetic episodic
memory, retrieval audits, and explicit relationship beliefs. It is an
experimental software mechanism. It does not model consciousness, felt emotion,
human autobiographical memory, or private reasoning.

## Public interfaces

| Interface | Purpose |
| --- | --- |
| `Memory` | Immutable current view of one episode, with authoritative facts and a separately reframeable interpretation |
| `EpisodeStore` | Append-only raw episodes, retrieval-access events, and interpretation-reframe events |
| `RetrievalQuery` | Declared query, day, participants, goals, seed, and experimental exclusions |
| `RetrievalRecord` | All candidates, every score component, exclusion reason, stable tie-break, and selected top-k |
| `RetrievalEngine` | Pure `rank` followed by transactional, idempotent `commit` |
| `Belief` / `BeliefLedger` | Bounded explicit proposition state with supporting and contradicting memory IDs |
| `MemoryRuntime` | Offline integration of storage, retrieval, beliefs, blocking, reframing, and checkpointing |
| `MemoryIntegration` | Optional Issue #9 hook: retrieve before action, stage after consequence, commit after a valid step |
| `NullMemoryIntegration` | Default no-op that preserves the accepted Issue #9 trajectory hash |

The schema registry can import `MEMORY_SCHEMA_MODELS` from
`memory.contracts` without importing the root schema module. It maps exactly
`memory.schema.json`, `retrieval-record.schema.json`, and `belief.schema.json`.

## Episode and fact boundaries

An episode records its source event/day, participants, copied environment facts,
optional interpretation, summary, outcome, resource cost, salience, goals,
condition tags, retrieval eligibility, and source-record provenance. All Pydantic
contracts reject undeclared fields and are frozen.

Raw episodes are never overwritten. The store has three append-only ledgers:

1. raw episode additions;
2. selected-retrieval access events; and
3. interpretation-reframe events.

`EpisodeStore.get` derives the current interpretation and retrieval count by
replaying those events. Reframing has no writable fact field, must cite existing
episode facts, and increments the interpretation revision exactly once. Blocking
changes only query exclusions; it cannot delete or modify storage.

## Deterministic retrieval

The default policy is in `configs/memory/default.yaml`. The offline relevance
function tokenizes public query and episode text and returns Jaccard overlap. It
makes no network call, uses no provider embedding, and persists no hidden state.

For candidate memory (m) and query (q):

\[
S(q,m)=F(q,m)\left(w_qQ+w_rR+w_sS+w_gG+w_pP\right)
\]

where:

- (Q) is lexical query relevance;
- (R=0.5^{age/half\_life}) is recency;
- (S) is stored salience;
- (G) is goal-set Jaccard overlap;
- (P) is participant-set Jaccard overlap; and
- (F\in\{0,1\}) is the declared experimental filter.

Scores are rounded to the configured fixed precision before ranking. Candidates
sort by descending total score and then ascending memory ID. The audit includes
every candidate, not only top-k. A candidate excluded because it is ineligible,
its memory ID is blocked, or one of its tags is blocked receives filter component
zero and a named exclusion reason.

An unrelated query can still retrieve a partner-related episode when its
measurable recency, salience, participant, or goal components outweigh relevance.
This is the operational definition of retrieval intrusion; it is not a claim
about involuntary human thought.

## Belief boundary

A belief exposes relationship-active, romantic, reciprocal, reliability,
expected-future-interaction, and confidence fields. Boolean propositions may be
`unknown`; absence of evidence is not encoded as false. Supporting and
contradicting evidence IDs are disjoint and must resolve to stored memories.
Confidence is bounded to `[0, 1]`.

The deterministic update adds evidence IDs and derives confidence from the
imbalance of supporting and contradicting counts. The frozen world uses the
generic proposition `relationship-interpretation`; the updater therefore does
not silently infer romance or reciprocity. A model-proposed update crosses a
separate `BeliefProposal` boundary, must be structured, bounded, and evidence
linked, and has no rationale or chain-of-thought field.

## Simulation transaction

Issue #9's v1 request, decision, step-record, state, and checkpoint schemas are
unchanged. With memory enabled:

1. `context_for_action` performs a pure rank and returns selected IDs plus public
   structured beliefs for the existing decision-request fields.
2. The model selects an action.
3. Issue #9 commits the action, debits resources, and applies its consequence.
4. `stage_after_consequence` creates a non-durable episode draft.
5. Public language is generated and the complete step record validates.
6. `commit_after_step` idempotently commits the retrieval audit/accesses,
   episodes, and evidence-linked belief update using the step-record hash.

A failure after ranking but before step validation leaves retrieval audits,
access counts, episodes, and beliefs unchanged. Enabled output runs add a
`memory-checkpoint.json` sidecar. Resume requires the simulation checkpoint and
the memory sidecar from the same completed-step boundary. The sidecars are
individually hash protected; a future orchestration layer may add a single
atomic pointer covering both files.

## Checkpoint and restoration

`MemoryRuntimeCheckpoint` contains the exact config and hash, raw store ledger,
belief versions, retrieval records, and active block lists. Nested store and
belief checkpoints are also hashed. Restore replays episodes, accesses,
reframes, and beliefs through integrity checks rather than assigning opaque
mutable dictionaries.

## Known limitations and confounds

- Lexical relevance is an offline test double, not semantic equivalence.
- Weight and salience choices can mechanically create or suppress intrusion;
  ablations and score audits are mandatory.
- Retrieval count is derived from selected-access events and is not a forgetting
  or reinforcement model.
- Generic relationship evidence does not establish romantic or reciprocal state.
- Participant labels in the synthetic world may be broad and can inflate the
  participant component; the component remains separately visible.
- Blocking and reframing are mechanism hooks for Issue #11, not evidence that a
  human intervention would have the same effect.
- Simulation and memory checkpoint files are paired sidecars, not one filesystem
  atomic write. The accepted recovery path restores the matching pair.
- No raw human data, clinical construct, subjective ground truth, or private
  chain-of-thought is requested or persisted.

## Verification

Tests cover append-only/idempotent storage, fixed-score auditing, stable ties,
blocking without deletion, fact-preserving reframing, evidence integrity,
confidence bounds, unrelated-query intrusion, transaction failure, checkpoint
restore, integrated resume, and the unchanged default Issue #9 trajectory hash.
