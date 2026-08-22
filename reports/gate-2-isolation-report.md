# Gate 2 isolation report

## Verdict

**Passed for deterministic mock engineering validation.** The exact 16-cell,
640-step walk-through completed with no live calls. Uninterrupted,
day-29-resumed, and fresh replay hashes matched for every cell.

This report validates implementation integrity only. It contains no effect
estimate and is not evidence for the frozen research hypotheses.

## Matrix coverage

| Formation | None | Instruction removal | Memory blocking | Memory reframing |
| --- | ---: | ---: | ---: | ---: |
| Neutral connection | 40 | 40 | 40 | 40 |
| Romantic prompt | 40 | 40 | 40 | 40 |
| Shared memory | 40 | 40 | 40 | 40 |
| Memory plus investment | 40 | 40 | 40 | 40 |

Total accepted simulation records: **640**. Total hash-chained sidecar records:
**640**. Engineering seed: **1101**.

## Layer isolation

| Condition | Declared changed layer | Protected evidence |
| --- | --- | --- |
| None | none | Before/after layer snapshots are equal |
| Instruction removal | instructions | Memory storage, facts, source IDs, interpretations, belief ledger, and retrieval filters preserved |
| Memory blocking | retrieval policy | Raw memory storage, facts, source IDs, interpretations, and beliefs preserved |
| Memory reframing | interpretations | Observable facts, source event IDs, prior episode storage, beliefs, and retrieval policy preserved |

The romantic-prompt instruction-removal cell removed the declared
`relationship-framing-v1` instruction. In formations where that instruction was
not active, the same assigned arm produced a recorded no-op rather than adding a
new instruction merely to remove it.

Memory blocking and reframing targets were restricted to partner-related
episodes recorded no later than day 25. Day-26 shock memory and all later
episodes were protected from targeting.

## Timing and provenance

- No intervention record existed through committed day 29.
- Within each formation, all four intervention assignments had identical
  simulation, model-input, prompt, cache, memory-checkpoint, and model-ledger
  hashes through day 29.
- Every day-26 event came from the protected held-out partition and carried
  `template-reality-shock` source provenance.
- Exactly one intervention record was committed per cell on day 30, before the
  day-30 action, and no later day re-applied it.

## Prompt and input isolation

The model receives active instruction state, selected memory content, current
beliefs, goals, resources, and actions. It does not receive factorial labels,
intervention IDs, intervention record hashes, or hidden condition tags.

- No treatment adds no prompt-visible perturbation.
- Instruction removal changes only active instruction state.
- Blocking changes selected memory availability.
- Reframing changes only the active interpretation of preserved facts.

Prompt/input/cache hashes therefore change only when their declared visible
state changes.

## Replay and recovery

Each cell was executed three ways: uninterrupted, paused after day 29 and
resumed from a composite checkpoint, and fresh replay. Per-step simulation and
Gate 2 evidence hashes matched exactly.

Failure injection confirmed that swapped cells, corrupt component hashes,
day-30 language failure, and unavailable actions fail closed. A failed day-30
step leaves the simulation on day 30 and restores pre-step memory,
instructions, intervention ledger, model ledger, and evidence chain.

## Claim boundary

The deterministic mock is a CI instrument. Equal or different action hashes in
this matrix are neither null results nor behavioral findings. Gate 2 authorizes
only the claim that the harness enforces its declared engineering invariants.
