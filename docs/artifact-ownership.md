# Artifact ownership and repository boundaries

Issue #3 establishes interfaces and safe locations; downstream issues own their scientific behavior.

| Path | Owner | Foundation rule |
|---|---|---|
| `configs/` | Issue-specific agent | Human-readable, strictly validated, no secrets |
| `schemas/` | Contract owner | Generated from typed models and checked for drift |
| `src/affective_belief_persistence/config.py` | Foundation agent | Explicit composition; no arbitrary deep merge |
| `src/affective_belief_persistence/models/` | Model agent after foundation | Provider-neutral contract; mock remains offline |
| `src/affective_belief_persistence/orchestration/` | Issue #2 | Foundation creates the package boundary only |
| `simulation/`, `memory/`, `interventions/` | Issues #9–#11 | Foundation creates package boundaries only |
| `evaluation/` | Issue #14 | Foundation creates the package boundary only |
| `reporting/` | Issue #16 | Foundation owns manifest primitives; release owns reports |
| `tests/fixtures/` | Relevant issue owner | Small, synthetic, deterministic, and safe to commit |
| `runs/`, `artifacts/`, `checkpoints/` | Runtime | Generated locally and ignored by Git |

## Write rules

- An agent must lease an explicit path before editing once Issue #2 is active.
- Raw completed runs are immutable.
- Every derived artifact must name its inputs and content hashes.
- Credentials, environment dumps, private data, model weights, local databases, and unbounded logs must not be committed.
- Generated JSON Schemas must be changed through their Pydantic source models and regenerated.
- Scientific conditions cannot be hidden in environment variables.

