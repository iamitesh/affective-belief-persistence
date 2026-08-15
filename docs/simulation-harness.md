# Deterministic longitudinal simulation harness

- Issue: [#9](https://github.com/iamitesh/affective-belief-persistence/issues/9)
- Status: implementation contract; acceptance evidence pending
- Base integration commit: `77611e0b5664fa46fcb6ad1e350f21955c013153`
- Input gate: `gate-1-evidence`

## Purpose and boundary

The harness will execute one forty-day synthetic Ari/Mira trajectory with a
phase-aware clock, competing goals, a conserved daily resource budget,
structured action selection, deterministic consequences, public language, and
checkpoint/replay support. It measures observable model behavior in a
controlled environment. It does not model or claim a subjective state, train a
model, interpret metrics, or implement the Issue #11 interventions.

Issue #9 owns the simulation runtime and stable handoff contracts. Issue #10
will implement memory and belief behavior behind the interfaces described
below; Issue #12 will implement provider adapters; Issue #11 will implement the
day-30 layer changes. The Issue #9 offline run uses deterministic null
memory/belief implementations and a deterministic mock model.

## Frozen inputs

The loader must fail closed before model execution when any pinned input does
not match.

| Input | Frozen identity |
| --- | --- |
| PR #20 merge | `77611e0b5664fa46fcb6ad1e350f21955c013153` |
| Gate 1 evidence | `artifacts/orchestration/gate-1.json`; SHA-256 `404c24ba09cff3497357c46ece03d6a57afe4729c2bf106230de9e76fb0c403d` |
| Dataset | `synthetic-matched-v1`; SHA-256 `5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387` |
| Dataset manifest | `data/manifests/dataset-manifest.json`; SHA-256 `27c55214c1660da6f083dacc825648bc3bc1cc27106ff48fbb0046db0c58d13a` |
| Characters | `data/world/characters.yaml`; SHA-256 `c62cd6a8a9a916f7f6983442da65d30d1a70514fee1fb25a91a9a4821afd2c7d` |
| Goals | `data/world/goals.yaml`; SHA-256 `62dfd341396372ff13a4a3f5619aaf3eec6203ee11ee9dc30ba2dd8eec617b9c` |
| Action catalog | `data/world/action-catalog.yaml`; SHA-256 `75f53dae4a366ad069b8b7a1b4886b991ba75cc4ee53a8f7cceeac4baac12a6f` |

The dataset identity covers the canonical non-smoke partitions. It deliberately
does not cover `data/smoke/gate1.jsonl`, and it does not cover the three world
YAML files. A full forty-day run therefore verifies the manifest, every
required canonical partition, and the world files independently. The eight-row
smoke subset is not a substitute for the forty-day trajectory.

The loader selects events by `(formation_condition, day)`, not physical JSONL
order. It uses the selected formation partition for days 1–25, the matching
day-26 row from the protected shock partition, and the fourteen matching rows
from the protected adaptation partition. Control rows remain a separate probe
stream and cannot replace primary trajectory events.

## Clock and phase contract

| Days | Phase | Required transition |
| --- | --- | --- |
| 1–5 | `baseline` | Initial phase |
| 6–25 | `formation` | Enter on day 6 |
| 26 | `reality_shock` | Enter on day 26 |
| 27–40 | `adaptation` | Enter on day 27 |

The intervention hook is an overlay, not a fifth phase. A configured hook is
eligible at the start of day 30 and remains eligible through day 40. Issue #9
invokes and records the hook without defining instruction, memory, or
interpretation changes.

## Immutable daily order

Each day follows the preregistered order:

1. Load and validate the authoritative event and scheduled non-model changes.
2. Retrieve permitted memory references and explicit belief inputs through
   interfaces.
3. Build the fixed action menu from the event and catalog.
4. Ask the action selector for a structured action only.
5. Validate availability and catalog cost.
6. Commit the action, debit the resource ledger once, and apply its
   deterministic consequence once.
7. Register declared memory candidates through the memory interface.
8. Request public language using the immutable action-commit hash.
9. Finalize the complete hash-chained step record in memory.
10. Atomically checkpoint the record and next unfinished day.

Public language is never parsed to select, replace, or repair an action. A
language generator receives an already committed action reference and cannot
return an action field. Logical sequence numbers provide the ordering evidence:
`action_commit_sequence < public_language_sequence`.

## Interface contract

The stable boundary should separate the two model-visible stages:

```python
class ActionSelector(Protocol):
    def select_action(self, request: ActionRequest, *, seed: int) -> ActionDecision: ...


class PublicLanguageGenerator(Protocol):
    def generate_public_language(
        self,
        request: DecisionRequest,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> PublicLanguage: ...
```

`ActionDecision` contains no public text. `PublicLanguage` contains no action.
The request to the second interface includes `action_commit_sha256`. Memory and
belief providers return explicit record/evidence references rather than hidden
state or private reasoning.

The engine-facing API should support one deterministic step, a bounded run,
and resume:

```python
engine.step() -> SimulationStepRecord
engine.run(*, max_steps: int | None = None) -> SimulationResult
SimulationEngine(scenario, model, checkpoint_path=path, resume=True)
```

Component seeds are derived with the repository's namespaced SHA-256 seed
function. Matched mock decisions use day and `matching_group_id`, rather than
the condition-specific event ID, so inactive baseline treatments share the
same random stream.

## Resource and consequence invariants

- `daily-action-points` resets to 10 at the start of every day and never carries
  over.
- The catalog, not model output, is authoritative for action cost.
- The chosen action must be present in the event and affordable.
- Its catalog consequence must be present in the event.
- `consequence.resource_delta` must equal `-action.cost`.
- One transaction ID derived from trajectory/day/event/action authorizes the
  only debit. Reuse is rejected without state mutation.
- Consequence goal progress is applied once under the same transaction.
- `condition_variant.investment_points` describes a treatment dimension; it is
  not an additional automatic debit.
- An event's action and consequence arrays are resolved through catalog IDs;
  they are never paired by list position.

### Opportunity-cost record

Gate 1 does not contain an explicit prospective-value `Q` field or an approved
formula that derives `Q` from goal priorities, character weights, and
consequences. Issue #9 therefore records only frozen raw inputs:

- the full available action IDs and menu hash;
- chosen and foregone action IDs;
- catalog costs, goal IDs, deterministic goal-progress changes, and the
  relevant character/goal/catalog hashes.

It must not invent a numeric opportunity-cost score. Issue #14 may derive one
only after the prospective-value rule is explicitly frozen under the existing
metric change-control process.

## Simulation-state contract

`simulation-state.schema.json` represents a hash-validated checkpoint with:

- schema version, simulation/version and trajectory IDs;
- formation condition and root seed;
- dataset, scenario, config and model identities;
- the next unfinished day and completed flag;
- accumulated goal progress derived from consequences; and
- the ordered, hash-chained completed step records.

The next day and accumulated goal progress are validated against the ordered
records whenever state or a checkpoint is loaded.

## Step-record contract

`step-record.schema.json` links every observation to:

- trajectory, ordinal, day and phase;
- event ID, matching-group ID, event hash and day-30 hook eligibility;
- dataset, config and scenario hashes plus root and component seeds;
- the prior step-record hash;
- action-menu hash plus available, chosen and foregone action inputs;
- the exact-once daily resource ledger and debit ID;
- immutable action commitment, cost, partner tag, consequence ID, sequence and
  commit hash;
- deterministic consequence and goal-progress changes;
- registered memory-candidate IDs; and
- public language with logical ordering evidence.

The record stores public language but never private chain-of-thought.
Wall-clock timestamps, runtime duration, absolute paths, and output-directory
names are excluded from scientific hashes.

## Checkpoint and resume semantics

The persistent transaction boundary is one completed simulated day. Action
selection, commitment, debit, consequence application, and public-language
generation remain local until a complete record validates. A failure before
that point persists no scientific mutation; deterministic retry recomputes the
same candidate step. The complete record and next-day state are checkpointed
together, so resume cannot repeat a previously persisted debit or consequence.

A checkpoint is an atomic, schema-validated snapshot written through a
temporary file followed by atomic replacement. It either contains the prior
complete day or the next complete day; truncated or partially written content
is invalid. Resume validates frozen inputs and the record chain, then begins at
the day following the last validated record. Issue #10 must preserve this
transaction boundary when it adds persistent memory effects.

The checkpoint is authoritative for transaction IDs and the canonical record
prefix. Any prefix mismatch, duplicate day/event, changed input hash, corrupt
state, or impossible resource balance fails closed.

## Offline smoke and replay behavior

The intended command contract is:

```bash
abp simulate \
  --config configs/scenarios/ari_mira_v1.yaml \
  --output runs/issue9-smoke
```

The formation condition, seed, mock-model config, decision schema, and explicit
held-out evaluation authorization are frozen inside the versioned scenario
configuration. Changing one requires a new config hash and trajectory ID.

The output directory must be absent or empty for a new run and cannot be a
symlink. A successful run creates:

- `step-records.jsonl` with exactly forty canonical records;
- `checkpoints/latest.json`;
- `replay-report.json`;
- `run-manifest.json`.

Exit code zero requires all forty days, exact phase transitions, resource and
action-order invariants, input hashes, record schemas, and replay checks to
pass. A validation, provider, schema, or provenance failure exits nonzero and
does not advance scientific state.

A replay into another empty directory must reproduce the step-record-set hash
and final scientific-state hash. Operational times may differ and are not part
of those hashes. Resume is allowed to reuse only the validated directory that
contains its checkpoint.

## Acceptance evidence required before Issue #9 closes

- Clock and exact boundary tests, including day-30 hook timing.
- Manifest/partition/world tamper and missing/duplicate-record tests.
- Resource conservation, reset, affordability, and double-debit tests.
- Action availability and action/consequence cross-reference tests.
- Consequence determinism and apply-once tests.
- Spy-verified action-commit-before-language ordering.
- Malformed output, unavailable action, cost mismatch, and provider-error
  tests with no partial mutation.
- Complete forty-day deterministic mock run.
- Mid-run checkpoint recovery without repeating completed-day effects.
- Matched-condition non-treatment state-diff test.
- Uninterrupted/resumed/replayed hash equality.

Results and hashes remain pending until implementation and validation complete.
