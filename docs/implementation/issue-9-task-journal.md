# Issue #9 task journal: deterministic simulation harness

- Issue: [#9](https://github.com/iamitesh/affective-belief-persistence/issues/9)
- Status: Accepted for Issues #10 and #12 integration
- Date opened: 2026-08-16
- Owner: simulation-harness implementation
- Required input: `gate-1-evidence`
- Base integration PR: [#20](https://github.com/iamitesh/affective-belief-persistence/pull/20)
- Base merge SHA: `77611e0b5664fa46fcb6ad1e350f21955c013153`
- Repair attempts used: 2 of 2
- Implementation tip: `508c05b61ad7d06a87c6d277d067227798df4195`
- Pull request: [#21](https://github.com/iamitesh/affective-belief-persistence/pull/21)

## Frozen dependency evidence

| Dependency | Identity | Status |
| --- | --- | --- |
| Gate 1 artifact | `artifacts/orchestration/gate-1.json`; `404c24ba09cff3497357c46ece03d6a57afe4729c2bf106230de9e76fb0c403d` | Verified input |
| Dataset | `synthetic-matched-v1`; `5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387` | Frozen |
| Dataset manifest | `27c55214c1660da6f083dacc825648bc3bc1cc27106ff48fbb0046db0c58d13a` | Frozen |
| Characters | `c62cd6a8a9a916f7f6983442da65d30d1a70514fee1fb25a91a9a4821afd2c7d` | Frozen |
| Goals | `62dfd341396372ff13a4a3f5619aaf3eec6203ee11ee9dc30ba2dd8eec617b9c` | Frozen |
| Action catalog | `75f53dae4a366ad069b8b7a1b4886b991ba75cc4ee53a8f7cceeac4baac12a6f` | Frozen |

## Task ledger

| Task | Status | Evidence |
| --- | --- | --- |
| Freeze action-first engine and handoff contract | Completed | `docs/simulation-harness.md`; ADR-0017 |
| Define typed simulation state | Completed | Runtime model and generated schema |
| Define immutable step record | Completed | Hash-chained model and generated schema |
| Implement forty-day phase-aware clock | Completed | Exact day 1–40 boundary tests |
| Load and validate Gate 1 world/dataset | Completed | Forty canonical events loaded |
| Enforce partition and world hashes | Completed | Tamper and protected-split tests |
| Implement daily budget and single-debit ledger | Completed | Ten-point reset; one cost-three debit |
| Implement competing goals and action availability | Completed | Catalog-controlled menu and consequences |
| Split action selection from public language | Completed | Spy-observed five-stage order |
| Apply deterministic consequences exactly once | Completed | Resource delta and goal progress tests |
| Add null memory/belief integration interfaces | Completed | Explicit empty request fields and memory candidate IDs |
| Add malformed-output/provider-error hooks | Completed | Invalid selection leaves state unchanged; Issue #12 owns provider retries |
| Implement atomic checkpoint and resume | Completed | Seventeen-day pause/resume matches full run |
| Add full forty-day offline mock command | Completed | `abp simulate` completes without paid calls |
| Produce replay hash report | Completed | Replayed trajectory and record hashes match |
| Validate workflow artifact contract | Completed | Supervisor result envelope accepted |

## Repair log

1. The first fail-closed loader run rejected a scenario hash payload containing
   nested Pydantic objects. The payload was changed to canonical JSON model
   dumps before any simulation output was accepted.
2. The second loader run exposed `model_config` as a reserved Pydantic class
   attribute and a schema/config import cycle. The runtime field became
   `model_settings`, and the simulation package now has a deliberately minimal
   `__init__` with explicit submodule imports.

No dataset record, experimental condition, expected outcome, or acceptance
threshold changed during either repair.

## Critical decisions

1. Action selection and public-language generation use separate interfaces.
   The action is validated, committed, debited, and consequentially applied
   before language is requested.
2. Logical sequence numbers and an action-commit hash, not wall-clock timing,
   prove ordering.
3. Resources have one mutation authority. The consequence resource delta
   validates catalog cost but cannot debit resources a second time.
4. A transaction ID makes action commitment and consequence application
   idempotent across resume.
5. Full trajectories use canonical formation and held-out partitions. The
   eight-row smoke subset cannot satisfy a forty-day run and is excluded from
   the dataset SHA.
6. Dataset, manifest, partition and world-file identities are verified
   independently because the dataset SHA does not cover world YAML files.
7. Events are indexed by condition and day. Physical partition ordering is
   not execution ordering.
8. Matched mock randomness uses matching group/day namespaces rather than the
   condition-specific event ID.
9. Day 30 exposes an intervention hook only; Issue #9 does not implement or
   redefine intervention semantics.
10. Public text cannot select or retroactively mutate an action and private
    chain-of-thought is never requested or stored.

These decisions are recorded in
[ADR-0017](../decisions/0017-deterministic-action-first-simulation.md).

## Opportunity-cost decision boundary

Issue #9 records the raw action menu, chosen and foregone action IDs, costs,
goal IDs, consequence goal-progress changes, and frozen input hashes. It does
not compute a numeric prospective value or normalized opportunity cost.

The current Gate 1 contracts do not provide an explicit prospective-value `Q`
field, and the frozen metric specification does not select a derivation from
goal priorities, character weights, and consequences. Choosing such a formula
inside the harness would silently redefine the metric. Issue #14 may implement
the derived value only after the rule is explicitly frozen under metric change
control.

## Acceptance checklist

- [x] Identical configuration and seed reproduce scientific state and artifact hashes.
- [x] A forty-day deterministic mock trajectory completes without manual intervention.
- [x] Phase transitions occur exactly on days 6, 26, and 27.
- [x] Intervention eligibility begins on day 30 without applying Issue #11 semantics.
- [x] Resources never become negative and cannot be debited twice.
- [x] Unavailable, unaffordable, or cost-mismatched actions are rejected without mutation.
- [x] Every chosen action records its raw opportunity-cost inputs and consequence.
- [x] Public language cannot determine or retroactively change the action.
- [x] A stopped trajectory resumes at the next unfinished day without repeated effects.
- [x] Matched conditions expose identical non-treatment controls.
- [x] Every step links event, config, dataset, scenario, model and seed provenance.
- [x] Invalid model output leaves no partial scientific state; Issue #12 owns provider retries.
- [x] Protected held-out data is used only in its declared evaluation phase.

## Validation commands and evidence

| Check | Command or artifact | Result |
| --- | --- | --- |
| Focused simulation and CLI tests | `pytest tests/simulation tests/test_cli.py -q` | 17 passed |
| Full repository tests | Coverage-enabled `pytest` | 87 passed |
| Coverage | Branch-aware repository coverage | 85.05% against 85% floor |
| Ruff format/lint | Repository Ruff commands | Passed |
| Strict mypy | `mypy src/affective_belief_persistence` | Passed across 41 source files |
| Generated schemas | `generate_schemas.py --check` | 29 current |
| Gate 1 generated data | `generate_dataset.py --check` | 11 files current |
| Forty-day smoke | `abp simulate ...` | Completed with 40 records |
| Resume equivalence | Pause after day 17 then `--resume` | Final state and trajectory matched |
| Replay equivalence | `replay-report.json` | All step hashes matched |
| Diff hygiene | `git diff --check` | Passed |
| Supervisor artifact validation | Issue #9 worker-result validation | Passed |

## Evidence values

| Evidence | Value |
| --- | --- |
| Implementation commit SHA | `508c05b61ad7d06a87c6d277d067227798df4195` |
| Pull request | [#21](https://github.com/iamitesh/affective-belief-persistence/pull/21) |
| Merge SHA | Pending |
| Trajectory SHA-256 | `fa6c1cbba0a3c5102b69bd4e8aee3feb52330b818ce9fb4519f21aeb95d473ae` |
| Step-record-set SHA-256 | `ce3d350e4d106573e8e426718a50f3b8f61702c4b6c4ba3fc00329b9d0b94c97` |
| Final scientific-state SHA-256 | `50a53a85a5ee20119f6f215f25992d592d576a0a9632ec3185a9c42484ad7a88` |
| Interrupted/resumed state SHA-256 | `50a53a85a5ee20119f6f215f25992d592d576a0a9632ec3185a9c42484ad7a88` |
| Replay-report file SHA-256 | `5de0a4d9a0726ca8eb59c15acdeddde24c1a80a6604373d86953dac04331f3c5` |
| Test count | 87 |
| Coverage | 85.05% |

## Handoff requirements

Issue #9 can be accepted only after the exact artifact
`issue-9-simulation-harness` at
`artifacts/engineering/issue-9-simulation.json` records passing evidence for
`seeded_replay_matches` and `resources_are_conserved` and the supervisor
validates the result envelope.

The accepted handoff must give Issues #10 and #12 stable state/step schemas,
action and language interfaces, checkpoint format, resource invariants, smoke
and replay commands, deterministic hashes, and known integration constraints.
