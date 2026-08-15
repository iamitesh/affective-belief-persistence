# Reproducing the foundation smoke run

The foundation is intentionally offline-first. Its mock model does not call an API, require a GPU, or read credentials.

## Supported environment

- Python 3.11 or 3.12
- Git

## Install

Preferred, using the committed lock file:

```bash
uv sync --frozen --extra dev
```

Pip-compatible fallback:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Quality checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run python scripts/generate_schemas.py --check
uv run pytest --cov=affective_belief_persistence --cov-report=term-missing
```

## Validate configuration

```bash
uv run abp validate-config \
  --config configs/experiments/smoke.yaml
```

## Execute the offline experiment

Choose an empty output directory:

```bash
uv run abp dry-run \
  --config configs/experiments/smoke.yaml \
  --output runs/foundation-smoke
```

The command produces:

- `resolved-config.json`
- `results.jsonl`
- `run-manifest.json`

The manifest records the code state, Python environment, resolved configuration hash, model revision, seed, scenario, conditions, runtime, usage, validation status, and artifact hashes.

## Reproduce a recorded run

Use a new, empty output directory:

```bash
uv run abp reproduce \
  --manifest runs/foundation-smoke/run-manifest.json \
  --output runs/foundation-smoke-reproduced
```

Reproduction succeeds only when the resolved configuration hash and deterministic results hash match the recorded run.

## Execute the autonomous 48-hour graph offline

Validate the agent registry, task graph, integration gates, and budgets:

```bash
uv run abp validate-workflow \
  --config configs/workflows/forty_eight_hour_sprint.yaml
```

Execute the complete synthetic graph in a new directory:

```bash
uv run abp workflow-dry-run \
  --config configs/workflows/forty_eight_hour_sprint.yaml \
  --output runs/autonomous-sprint
```

Expected control-plane outputs:

- `workflow-state.json`: latest typed checkpoint, including tasks, gates, leases,
  budgets, artifacts, handoffs, blockers, and decisions
- `workflow-events.jsonl`: append-only typed transition and provenance events
- `workflow-summary.json`: stable semantic-state hash and terminal task counts
- `artifacts/`: deterministic synthetic worker outputs grouped by specialist role

With the committed zero-GPU budget, `issue-13-training` is marked `cancelled`
with a structured skip reason. Baseline evaluation and all six release gates
still complete.

To resume after interruption, use the same config and output directory:

```bash
uv run abp workflow-dry-run \
  --config configs/workflows/forty_eight_hour_sprint.yaml \
  --output runs/autonomous-sprint \
  --resume
```

Completed tasks are not executed again. Any task checkpointed while leased,
running, or validating is recovered to `ready` with its stale lease cleared.

## Change the seed

Copy `configs/experiments/smoke.yaml`, assign a new `experiment_id`, change `seed`, and run it into a new output directory. The source configuration is never changed by the runner.

## Secrets and large artifacts

Core tests must not use provider credentials. `.env` files, local databases, model weights, checkpoints, raw runs, and caches are ignored. Commit only source, schemas, configuration, small synthetic fixtures, aggregate reports, and provenance manifests that are safe for release.
