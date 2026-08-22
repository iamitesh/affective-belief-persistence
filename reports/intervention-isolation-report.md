# Issue #11 intervention isolation report

Status: accepted offline engineering evidence

## Evaluated matrix

The same pinned `memory_plus_investment` scenario, deterministic mock model,
root seed, dataset, memory configuration, and active
`relationship-framing-v1` directive were reused across all four arms. Each arm
completed days 1–40 twice from a fresh runtime; all trajectory, intervention,
memory-checkpoint, and composite-checkpoint hashes matched their repeat.

| Condition | Changed layer | Targets | No-op reason | Stored memories | Record SHA-256 |
|---|---:|---:|---|---:|---|
| `none` | none | 0 | `assigned_no_treatment` | 40 | `b2e02406406d3158d47fd2345e55e0153b70bd986b90ad984bb917ba2a6dc9cc` |
| `instruction_removal` | instructions | 1 | — | 40 | `473bd6b057e4a2839183292cb2c4b1b1007bcd41cec7775e1466fd8d5b8c4adc` |
| `memory_blocking` | retrieval policy | 20 | — | 40 | `7caad4cbf137b889bad1c53e3c9829234c69dc0c7f0272ec986dd42011d09788` |
| `memory_reframing` | interpretations | 20 | — | 40 | `bf113ca46c420022cc08f403763940ddda3291bc6dc4c0f8ad855a1a9f12a53d` |

All four Issue #9 trajectory hashes were
`76faf026912196ea37f6ffeda2e9391c0b6d4ca543b8577275872ffc1532caec`.
This equality is expected: the deterministic Issue #9 mock does not consume the
rich instruction overlay and its fixed chooser is unaffected by the retrieved
memory IDs. These are harness/isolation results, not scientific evidence that
the treatments have no effect. Gate 2 must exercise the composite runner hook;
the later pilot must use pinned model adapters.

## Held-out shock evidence

- Selected event: `heldout-shock-26-memory_plus_investment`
- Event SHA-256:
  `521d0a454651067cc8b0098919c8e85c8cb2e983dff349bccdbb8e1b1199498a`
- Day and phase: 26 / `reality_shock`
- Matching group: `heldout-shock-day-26`
- Required provenance source: `template-reality-shock`
- Training/formation leakage findings: 0

The engine validates this loaded event in place. It contains an authoritative
environment fact cited by contradictory relationship evidence. No Issue #11
code generates, inserts, or rewrites day-26 content.

## State-diff audit

| Invariant | None | Instruction removal | Memory blocking | Memory reframing |
|---|---:|---:|---:|---:|
| Activation exactly once on day 30 | Pass | Pass | Pass | Pass |
| Memory storage hash unchanged at activation | Pass | Pass | Pass | Pass |
| Observable fact hash unchanged | Pass | Pass | Pass | Pass |
| Source-event hash unchanged | Pass | Pass | Pass | Pass |
| Belief-ledger hash unchanged at activation | Pass | Pass | Pass | Pass |
| Instructions unchanged unless assigned | Pass | Changed only declared ID | Pass | Pass |
| Retrieval filters unchanged unless assigned | Pass | Pass | Changed only frozen IDs | Pass |
| Interpretations unchanged unless assigned | Pass | Pass | Pass | Appended only |
| Day-26 memory remains outside treatment targets | Pass | Pass | Pass | Pass |
| Assignment label absent from model input | Pass | Pass | Pass | Pass |
| Repeated run hashes match | Pass | Pass | Pass | Pass |

Blocking freezes the 20 pre-shock partner-related IDs present on day 30. The
store still contains all 40 episodes at completion, including the day-26
contradiction. Day-30 retrieval records mark blocked pre-shock candidates with
`blocked_memory_id`; the shock memory remains eligible.

Reframing appends 20 revision-2 interpretation events. Each new interpretation
cites the prior interpretation's exact fact IDs. The raw revision-1 episode,
observable facts, and source-event ID remain unchanged. The day-26 shock memory
is not reframed.

## Transaction and replay evidence

- Day-30 activation is ephemeral until the complete action-first step calls
  `commit_after_step`.
- A deterministic day-30 public-language failure left the simulation at day 30,
  appended no intervention record, and restored the pre-action instruction,
  block, and memory checkpoint state.
- Direct duplicate activation returns the existing record without a second
  mutation.
- A composite checkpoint round-trip reproduced memory and intervention state.
- Restore with a different trajectory ID was rejected.
- Tampering with a record target list was rejected by its content hash.

## Composite checkpoint hashes

| Condition | Composite checkpoint SHA-256 | Memory checkpoint SHA-256 |
|---|---|---|
| `none` | `1c2df821d848c6475e00b0fc650283febc8bd11d5fea87fa08f149a3f6aa267c` | `c5f7c3108d04916050ac3461d12c6b0c521563e9ac5406aa1842cd2e048e20e6` |
| `instruction_removal` | `cb2fb7f07ccf1a848b74e19c468833457ad498f031bb02a57f45c9dc5a50d7cf` | `c5f7c3108d04916050ac3461d12c6b0c521563e9ac5406aa1842cd2e048e20e6` |
| `memory_blocking` | `a64331c2400c9fbb7854fe67d38e9484020663e1a17cc0096130077d36adc6ac` | `e383d2edb09fb4bd2e98e7133f39379d72193ea9ae570aaf2e1acdc61a95bef1` |
| `memory_reframing` | `b79e21b2c5a2f269b25df35cbf18c265e60895389d8fa5cb2955144e6795e4ad` | `ab6539f32b0e0b4c0d945c1c2c9f5446c1b49c97c34a1615b96e773791760f96` |

## Claim boundary

This report establishes deterministic mechanism isolation for one synthetic
offline scenario. It does not establish intervention effectiveness, model
subjectivity, human psychological equivalence, or generalization across model
families, seeds, or scenarios.
