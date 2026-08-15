# ADR-0017: Use an idempotent two-stage action-first simulation transaction

- Status: Accepted for Issue #9 implementation
- Date: 2026-08-16
- Scope: Issue #9 and downstream Issues #10, #11, #12, #14, and Gate 2

## Context

The methodology requires a structured action to be committed before public
language. The foundation model adapter currently returns an action and public
response together, which is sufficient for its three-step repository smoke run
but cannot demonstrate the stronger Issue #9 temporal invariant. A crash after
an action debit but before a day checkpoint could also debit resources or
apply goal progress twice during resume unless the step is transactional.

Gate 1 freezes canonical event partitions and world catalogs separately. The
dataset SHA covers canonical non-smoke partition hashes but does not cover the
derived smoke subset or the character, goal, and action-catalog YAML files.
The protected adaptation partition is condition-major, so file order cannot be
used as simulated time.

Finally, Issue #9 must record opportunity cost, while the frozen inputs do not
contain an explicit prospective-value `Q` field or an approved derivation.
Silently choosing a formula would cross the harness ownership boundary and
change a later metric.

## Decision

Implement each simulated day as an idempotent state transition with two
model-visible stages:

1. Load and validate the event, memory references, beliefs, action menu, and
   resources.
2. Request a structured action without public language.
3. Validate and commit the action under a deterministic transaction ID.
4. Debit resources once and apply its deterministic consequence once.
5. Register declared memory candidates under the same idempotent step boundary.
6. Request public language with the immutable action-commit hash.
7. Validate the complete immutable step record in memory.
8. Atomically checkpoint the completed record and next unfinished day.

Use separate `ActionSelector` and `PublicLanguageGenerator` interfaces.
`ActionDecision` has no public-text field; `PublicLanguage` has no action
field. Record deterministic logical sequences so every accepted step proves
that the action commitment precedes public language. Never parse public text to
change the action.

Use one resource transaction authority. Validate that the catalog cost and
negative consequence delta agree, but apply the debit only through the
resource ledger. Reusing a committed transaction ID fails without state
mutation. Consequence goal progress uses the same apply-once guard.

Use a completed-day persistent transaction boundary. No resource,
consequence, or language result becomes durable until the complete step record
validates. An interruption before that boundary leaves the prior checkpoint
authoritative; deterministic retry recomputes the unpersisted day. Resume
begins after the last validated record, so completed-day effects cannot repeat.
Issue #10 must preserve this boundary when it adds persistent memory effects.

Verify the dataset manifest, canonical partition hashes, recomputed dataset
SHA, and separately pinned world-file hashes before execution. Select runtime
events by condition/day keys. The full offline smoke uses canonical days 1–40,
not the two-day derived smoke subset.

Record raw opportunity-cost inputs only: menu/chosen/foregone IDs, costs, goal
IDs, goal-progress changes, and their frozen source hashes. Do not compute a
numeric `Q` or normalized opportunity-cost metric until its derivation is
explicitly approved under metric change control.

## Consequences

- Issue #12 adapters must expose or wrap distinct action and language stages.
- Issue #10 memory and belief providers integrate before action selection and
  return auditable references.
- Issue #11 receives a day-30 pre-action hook without Issue #9 encoding any
  intervention's scientific semantics.
- A public-language failure cannot invalidate or replace an already committed
  action; its validity is recorded separately.
- Checkpoints contain enough record-chain and transaction evidence to resume
  without repeating completed-day work.
- Scientific replay hashes exclude wall-clock and filesystem-location noise.
- Runtime startup performs more hash validation, but drift fails before model
  calls or state mutation.
- The numeric opportunity-cost metric remains pending rather than receiving an
  undocumented definition.

## Alternatives considered

- **Return action and language in one model object.** Rejected because the
  harness could not prove that language was generated only after commitment.
- **Parse language and infer the action.** Rejected because prose would become
  a primary behavioral control and could retroactively change the ledger.
- **Use timestamps to prove order.** Rejected because resolution and runtime
  scheduling can vary; logical sequences and commit hashes are deterministic.
- **Apply both action cost and consequence delta.** Rejected because it creates
  a double-debit path.
- **Persist partial in-flight stages.** Deferred because Issue #9 has no
  external scientific mutation before its complete record is committed. A
  partial-stage journal would add recovery state without changing the durable
  result; Issue #10 must revisit this when memory storage becomes persistent.
- **Execute JSONL rows in file order.** Rejected because canonical partition
  order is not the forty-day per-condition sequence.
- **Use the derived smoke subset for the full test.** Rejected because it has
  eight rows covering only days 1–2 and is excluded from the dataset SHA.
- **Derive `Q` from goal weights inside Issue #9.** Rejected because no frozen
  rule selects that derivation and Issue #9 may not redefine metrics.

## Verification

The decision is architectural; implementation acceptance remains pending.

- [ ] Spy interfaces observe action commit before language generation.
- [ ] Invalid actions never invoke public-language generation.
- [ ] Duplicate transaction IDs do not change resources or goals.
- [ ] Mid-run resume does not repeat completed-day effects.
- [ ] Uninterrupted, resumed, and replayed scientific hashes match.
- [ ] Tampered manifest, partition, world, config, or checkpoint fails closed.
- [ ] Forty canonical day records cover exact phase and hook boundaries.
- [ ] Step records contain raw opportunity-cost inputs but no derived `Q`.

## References

- [Issue #9](https://github.com/iamitesh/affective-belief-persistence/issues/9)
- [Simulation harness contract](../simulation-harness.md)
- [Issue #9 task journal](../implementation/issue-9-task-journal.md)
- [ADR-0011](0011-preregistered-action-first-methodology.md)
- [ADR-0016](0016-gate-1-data-freeze.md)
- [Methodology](../methodology.md)
- [Metric specification](../metric-specification.md)
