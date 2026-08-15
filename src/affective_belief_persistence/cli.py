"""Command-line interface for the offline research foundation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel, ValidationError

from affective_belief_persistence.config import ConfigError, find_project_root, load_run_config
from affective_belief_persistence.orchestration.scheduler import OrchestrationError, Supervisor
from affective_belief_persistence.orchestration.workflow import (
    WorkflowDefinitionError,
    load_workflow_definition,
)
from affective_belief_persistence.runner import RunnerError, execute_dry_run, reproduce_run
from affective_belief_persistence.schemas import SCHEMA_MODELS


def _schema_text(model: type[BaseModel]) -> str:
    schema_method = model.model_json_schema
    return json.dumps(schema_method(), indent=2, sort_keys=True) + "\n"


def validate_schemas(root: Path) -> list[str]:
    failures: list[str] = []
    for filename, model in SCHEMA_MODELS.items():
        path = root / "schemas" / filename
        expected = _schema_text(model)
        if not path.is_file():
            failures.append(f"missing schema: {filename}")
        elif path.read_text(encoding="utf-8") != expected:
            failures.append(f"stale schema: {filename}")
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_config = subparsers.add_parser("validate-config")
    validate_config.add_argument("--config", type=Path, required=True)

    subparsers.add_parser("validate-schemas")

    dry_run = subparsers.add_parser("dry-run")
    dry_run.add_argument("--config", type=Path, required=True)
    dry_run.add_argument("--output", type=Path, required=True)

    reproduce = subparsers.add_parser("reproduce")
    reproduce.add_argument("--manifest", type=Path, required=True)
    reproduce.add_argument("--output", type=Path, required=True)

    validate_workflow = subparsers.add_parser("validate-workflow")
    validate_workflow.add_argument("--config", type=Path, required=True)

    workflow = subparsers.add_parser("workflow-dry-run")
    workflow.add_argument("--config", type=Path, required=True)
    workflow.add_argument("--output", type=Path, required=True)
    workflow.add_argument("--resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-config":
            loaded_run = load_run_config(args.config)
            print(f"valid config {loaded_run.resolved.experiment_id}: {loaded_run.config_sha256}")
            return 0
        if args.command == "validate-schemas":
            root = find_project_root()
            failures = validate_schemas(root)
            if failures:
                raise RunnerError("; ".join(failures))
            print(f"verified {len(SCHEMA_MODELS)} generated schemas")
            return 0
        if args.command == "dry-run":
            manifest = execute_dry_run(args.config, args.output)
            print(f"completed {manifest.run_id}: {manifest.result_set_sha256}")
            return 0
        if args.command == "reproduce":
            manifest = reproduce_run(args.manifest, args.output)
            print(f"reproduced {manifest.run_id}: {manifest.result_set_sha256}")
            return 0
        if args.command == "validate-workflow":
            loaded_workflow = load_workflow_definition(args.config)
            print(
                f"valid workflow {loaded_workflow.definition.workflow_id}: "
                f"{loaded_workflow.config_sha256}"
            )
            return 0
        if args.command == "workflow-dry-run":
            loaded_workflow = load_workflow_definition(args.config)
            summary = Supervisor(loaded_workflow, args.output, resume=args.resume).run()
            print(f"{summary.status} {summary.workflow_id}: {summary.state_sha256}")
            return 0 if summary.status == "completed" else 2
    except (
        ConfigError,
        OrchestrationError,
        RunnerError,
        ValidationError,
        WorkflowDefinitionError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2
