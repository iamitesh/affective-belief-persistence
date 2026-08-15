# Issue #5 task journal: research methodology

- Issue: [#5](https://github.com/iamitesh/affective-belief-persistence/issues/5)
- Status: Accepted for Gate 0
- Started: 2026-08-15
- Protocol: `abp-methodology-v1.0.0`
- Protocol bundle SHA-256:
  `1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb`
- Owner: methodology agent
- Repair passes used: 0 of 2

## Task ledger

| Task | Status | Evidence |
| --- | --- | --- |
| Freeze central and secondary questions | Completed | Six-field RQ table in `docs/methodology.md` |
| Preserve and operationalize H1–H6 | Completed | Versioned v0/v1 traceability table; one comparison and metric per hypothesis |
| Define unit, phases, and sampling assumptions | Completed | Trajectory unit, paired model/seed block, days 1–40 |
| Define IV, DV, controls, and nuisance variables | Completed | Variable and handling tables in methodology |
| Enforce action before language | Completed | Protocol order plus schema constant and automated test |
| Separate facts and interpretations | Completed | Distinct fact accuracy and interpretation support fields/metrics |
| Freeze metric formulas | Completed | Numerator, denominator, range, missing behavior, baseline, aggregation, and direction for every metric |
| Define recovery | Completed | Day-26 origin, `E≤0.10` for two consecutive days, censor at 15 |
| Specify reduced pilot | Completed | 4×4×1×2 = 32, explicitly exploratory |
| Specify primary matrix | Completed | 4×4×2×10 = 320, confirmatory after gates |
| Include every pilot pairing | Completed | Cartesian-product test produces all 16 cells for seed 1101 |
| Freeze matching and ablations | Completed | Ten controls plus no-memory, blocked-memory, shuffled-retrieval diagnostics |
| Freeze repeated analysis | Completed | Trajectory summaries, paired blocks, supportive clustered GEE |
| Freeze uncertainty/multiplicity | Completed | Stratified block bootstrap, sign-flip test, Holm H1–H6 family |
| Freeze invalid/missing/retry rules | Completed | One repair, objective exclusions, pairwise missingness, bounded sensitivities |
| Freeze budget and stop rules | Completed | Pilot 1,600 calls/12h; primary 16,000 calls/48h; integrity stops |
| Make configs machine-valid | Completed | Optional strict `design` model and generated experiment/resolved schemas |
| Preserve smoke compatibility | Completed | `smoke.yaml` resolves with `design=None` |
| Add deterministic fixtures | Completed | Range/direction and recovery tests in `tests/methodology/` |

## Critical decisions

1. Primary inference uses one complete trajectory as the experimental unit;
   repeated days are not independent samples.
2. The same seed is reused across all 16 cells, enabling paired contrasts inside
   fixed model-family/seed blocks.
3. H3 uses positive excess-action AUC as its one primary metric because it
   captures both magnitude and duration without a second hypothesis test.
4. H1's language component uses a frozen deterministic label after action; no
   human reads prose to assign the primary value.
5. H5 defines coherent adaptation as a conjunctive behavioral/fact/
   interpretation criterion rather than a subjective quality judgment.
6. The pilot expansion gate uses integrity, isolation, variance, safety, and
   budget only—never promising effects.
7. The optional trajectory adapter and diagnostic ablations stay outside the
   320 confirmatory trajectories.
8. Primary conclusions are limited to the pinned model revisions and synthetic
   scenarios; seeds do not imply population sampling.

ADR-0011 records the durable methodology decision and alternatives.

## Approved ownership exception

The generated experiment schema is sourced from
`src/affective_belief_persistence/schemas.py`. The supervisor approved a narrow,
backward-compatible edit to that file even though the initial Issue #5 lease
listed only the generated schema and `config.py`. Hand-editing generated JSON
would have violated the repository drift contract. The change only adds
optional experiment-design models and the matching optional resolved field; it
does not modify orchestration or safety contracts.

## Validation evidence

Commands executed from the repository root:

```text
.venv/bin/pytest -q tests/methodology tests/test_config.py
..................                                                       [100%]
18 passed

.venv/bin/ruff check src/affective_belief_persistence/schemas.py \
  src/affective_belief_persistence/config.py tests/methodology
All checks passed!

.venv/bin/pytest -q --ignore=tests/test_repository_policy.py
62 passed, 1 failed (schema drift only; see integration note below)
```

`mypy` was invoked three times, including with an isolated cache directory, but
the local executable terminated immediately with exit 135 and no diagnostic.
This is recorded as a tool/runtime blocker for the integration agent to retry;
ruff and runtime tests passed.

### Parallel integration note

The schema generator was run into an isolated temporary directory. Only the
Issue #5-owned `experiment-config.schema.json` and
`resolved-run-config.schema.json` were applied. During the parallel Issue #6
write, the generator also reported pending drift in `artifact.schema.json`,
`workflow-event.schema.json`, and `workflow-state.schema.json`; those files were
not overwritten. The one non-focused test failure is exactly the CLI global
schema check naming those three safety-owned outputs. The parent integration
pass must regenerate/verify all schemas after Issue #6 stops writing.

The protocol hash was recomputed after validation using the canonicalization
rule in `docs/preregistration.md`; it matched the recorded value.

## Acceptance checklist

- [x] Every hypothesis maps to one primary comparison and metric.
- [x] Formation and intervention effects are separately identifiable.
- [x] Action precedes public language.
- [x] Fact correction is separate from relationship interpretation.
- [x] Recovery threshold and time origin are preregistered.
- [x] Exclusions are outcome-blind.
- [x] Pilot is explicitly exploratory.
- [x] Repeated measurements are handled at the trajectory/block level.
- [x] A matched neutral-domain control is specified.
- [x] Pilot and primary matrix counts are machine-validatable.
- [x] No primary value requires subjective reading of prose.
- [x] All 16 pilot pairings have a deterministic walk-through case.
- [x] Global schema drift check passes after parallel Issue #6 integration.
- [x] `mypy` succeeds in the integration environment.
- [x] Gate 0 reviewer and Issue #6 reviewer sign off.

## Parent integration evidence

On 2026-08-15 the supervisor regenerated all shared schemas after Issues #5 and
#6 became idle, repaired the README terminology finding, and ran the complete
repository validation suite. Gate 0 accepted protocol
`abp-methodology-v1.0.0` with bundle SHA-256
`1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb`.
The environment's installed compiled mypy `1.20.2` crashed during import with
exit 135, including for `--version`; an isolated mypy `1.18.2` run exposed and
then verified the repair of one heterogeneous-collection annotation. The final
strict result was `Success: no issues found in 28 source files`.

## Deliverables

- `docs/methodology.md`
- `docs/preregistration.md`
- `docs/metric-specification.md`
- `docs/analysis-plan.md`
- `configs/experiments/pilot.yaml`
- `configs/experiments/primary.yaml`
- `schemas/experiment-config.schema.json`
- `schemas/resolved-run-config.schema.json`
- `src/affective_belief_persistence/schemas.py`
- `src/affective_belief_persistence/config.py`
- `tests/methodology/test_protocol_configs.py`
- `tests/methodology/test_metric_fixtures.py`
- `docs/decisions/0011-preregistered-action-first-methodology.md`

## Downstream handoff

Issues #7–#14 receive the frozen unit, phase schedule, factorial levels, seeds,
matching tolerances, held-out version, action-order invariant, exact metrics,
retry/exclusion rules, required ablations, and analysis plan. Gate 0 must combine
this methodology with the Issue #6 safety stop conditions and record the final
commit plus protocol hash before any empirical primary output is inspected.
