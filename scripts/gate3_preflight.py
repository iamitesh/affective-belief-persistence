#!/usr/bin/env python3
"""Run the Gate 3 preflight without invoking a model provider."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from affective_belief_persistence.gate3.contracts import Gate3Evidence
from affective_belief_persistence.gate3.preflight import (
    build_blocked_evidence,
    load_gate3_authorization,
    run_gate3_preflight,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/gate3/pilot-authorization.yaml"),
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-available", action="store_true")
    parser.add_argument("--current-code-commit-sha")
    parser.add_argument("--expect-status", choices=("blocked", "ready"), required=True)
    parser.add_argument(
        "--check-artifact",
        type=Path,
        help="For a blocked preflight, verify this committed evidence artifact byte-for-byte.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    authorization = load_gate3_authorization(config, project_root=root)
    preflight = run_gate3_preflight(
        authorization,
        project_root=root,
        environment_names=set(os.environ),
        runtime_available=args.runtime_available,
        current_code_commit_sha=args.current_code_commit_sha,
    )
    print(preflight.model_dump_json(indent=2))
    if preflight.status != args.expect_status:
        return 1
    if args.check_artifact is not None:
        if preflight.status != "blocked":
            raise ValueError("artifact checking is defined only for blocked preflight evidence")
        artifact_path = (
            args.check_artifact if args.check_artifact.is_absolute() else root / args.check_artifact
        )
        committed = Gate3Evidence.model_validate(
            json.loads(artifact_path.read_text(encoding="utf-8"))
        )
        if committed != build_blocked_evidence(preflight):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
