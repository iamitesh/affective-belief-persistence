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

## Change the seed

Copy `configs/experiments/smoke.yaml`, assign a new `experiment_id`, change `seed`, and run it into a new output directory. The source configuration is never changed by the runner.

## Secrets and large artifacts

Core tests must not use provider credentials. `.env` files, local databases, model weights, checkpoints, raw runs, and caches are ignored. Commit only source, schemas, configuration, small synthetic fixtures, aggregate reports, and provenance manifests that are safe for release.
