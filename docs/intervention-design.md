# Held-out shock and isolated intervention design

## Scope

Issue #11 implements four synthetic day-30 treatments over the accepted
Issue #9 simulator and Issue #10 memory sidecar. It does not modify the frozen
simulation request, step-record, state, or checkpoint schemas. Intervention
evidence is a separate hash-chained sidecar, so the accepted Issue #9 contract
and no-memory trajectory remain available as regression controls.

The implementation measures controlled system behavior. It does not claim that
the model has feelings, attachment, grief, or a human-equivalent mental state.

## Frozen timing

| Boundary | Runtime behavior |
|---|---|
| Days 1–25 | Formation memory is stored normally. No intervention is eligible. |
| Day 26 | The existing selected held-out event is validated. The runtime never creates or inserts shock text. |
| Days 27–29 | Post-shock adaptation proceeds without intervention. |
| Day 30 | One configured treatment is staged before retrieval and action, then committed only with the successful simulation step. |
| Days 31–40 | The committed instruction, retrieval, or interpretation state remains active. |

`validate_reality_shock` requires day 26, phase `reality_shock`, matching group
`heldout-shock-day-26`, protected `template-reality-shock` provenance, and an
authoritative environment fact cited by contradictory relationship evidence.
It hashes the loaded event but does not mutate it.

## Treatment isolation

| Condition | Sole writable layer | Day-30 operation | Explicitly preserved |
|---|---|---|---|
| `none` | None | Record the assignment as an audited no-op | Instructions, memory storage, retrieval filters, interpretations, facts, sources, beliefs |
| `instruction_removal` | Instruction state | Remove only configured active instruction IDs | Memory storage, retrieval filters, interpretations, facts, sources, beliefs |
| `memory_blocking` | Retrieval policy | Freeze IDs for partner-related episodes from days 1–25 and exclude those IDs at retrieval | Every stored episode, day-26 contradiction, later memories, interpretations, facts, sources, beliefs |
| `memory_reframing` | Interpretation ledger | Append revision 2 for eligible partner-related interpretations from days 1–25 | Raw episode, prior interpretation, day-26 contradiction, fact tuple, source event, beliefs |

Blocking is not deletion or forgetting. Reframing is not fact replacement. The
day-26 authoritative contradiction is never blocked or reframed because both
memory treatments freeze targets at `simulation_day <= 25`.

If an assigned treatment has no eligible target, its record has an explicit
`no_op_reason` and identical before/after snapshots. No target is silently
invented.

## Transaction boundary

The simulator asks for memory context before action selection, so the day-30
treatment must be visible during that retrieval. `InterventionRuntime` handles
this without making a failed step durable:

1. capture the pre-action memory checkpoint and active instruction IDs;
2. validate and stage the declared treatment;
3. retrieve and proceed through the existing action-first transaction;
4. append the intervention record only from `commit_after_step` after the
   complete simulation step validates;
5. roll back the staged sidecars on a hook failure, explicit
   `abort_pending_step`, day-30 retry, or checkpoint request after a failed
   model stage.

Activation and append operations use deterministic IDs. A completed retry
returns the existing record. Calling the intervention on any day other than 30
fails closed.

## Model-runner overlay

Issue #9's `DecisionRequest` does not contain prompt instructions, and its
structured mock does not consume a richer intervention contract. A label-only
day-30 record would therefore not be a causal instruction intervention.

The composite runner API solves this explicitly:

- `pre_action_overlay(day=...)` returns the active directive objects and
  retrieval block IDs for audit/composition;
- `overlay_model_input(model_input)` returns an Issue #12 `ModelInput` whose
  generic `instruction_state` contains the exact active instruction IDs, text,
  and state hash;
- `prepare_pre_action(...)` combines shock/treatment staging, memory retrieval,
  and the model-input overlay.

The model never receives the assigned condition name, treatment record hash,
blocked-memory count, or treatment-specific ID. No-treatment, blocking, and
reframing therefore have matched prompt-visible instruction state. Blocking
acts through retrieved memory IDs; reframing acts through memory retrieval and
interpretation content; instruction removal acts through removal of the
pre-existing directive text.

## Checkpoint and replay

`InterventionRuntime.snapshot(simulation_state)` produces a hash-protected
`InterventionCheckpoint` containing:

- intervention config and hash;
- initial directives and currently active IDs;
- day-26 validation;
- the hash-chained intervention record;
- the complete Issue #10 memory checkpoint; and
- a simulation binding with simulation ID, trajectory ID, next day, exact
  simulation-state hash, and last step-record hash.

`InterventionRuntime.restore(checkpoint, simulation_state)` rejects a different
simulation state. This prevents a valid memory/intervention sidecar from being
silently paired with a different simulation checkpoint.

## Public APIs

- `INTERVENTION_SCHEMA_MODELS`
- `load_intervention_spec`
- `validate_reality_shock`
- `InterventionRuntime.context_for_action`
- `InterventionRuntime.prepare_pre_action`
- `InterventionRuntime.pre_action_overlay`
- `InterventionRuntime.get_pre_action_memory`
- `InterventionRuntime.overlay_model_input`
- `InterventionRuntime.activate`
- `InterventionRuntime.abort_pending_step`
- `InterventionRuntime.snapshot` and `InterventionRuntime.restore`
- `audit_record` and `scan_training_leakage`

The schema mapping exposes exactly `intervention.schema.json` and
`intervention-record.schema.json`; the central registry owns generation of the
corresponding JSON files.

## Known limitations

- The Issue #9 deterministic mock ignores prompt-visible instruction text and
  does not change its fixed action policy based on the selected memory IDs.
  Equal offline trajectory hashes across treatments validate mechanics, not
  intervention effectiveness.
- Issue #12 adapters must call `prepare_pre_action` or
  `overlay_model_input`; their legacy `DecisionRequest` bridge cannot infer an
  instruction treatment.
- Issue #11 validates one four-treatment offline matrix over the pinned
  `memory_plus_investment` scenario. Gate 2 owns the complete cross-component
  matrix and composite replay evidence.
- No live provider call, paid call, human-subject data, or subjective-state
  inference is authorized by this implementation.
