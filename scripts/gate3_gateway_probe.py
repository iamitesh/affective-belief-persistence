#!/usr/bin/env python3
"""Verify a Gate 3 gateway manifest against optional metadata-only evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from affective_belief_persistence.determinism import sha256_file
from affective_belief_persistence.gate3.contracts import (
    GatewayMetadataSnapshot,
    GatewayProbeResult,
)
from affective_belief_persistence.gate3.gateway import (
    load_gateway_manifest,
    probe_gateway_identity,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/gate3/qwen25-vllm-gateway-candidate.yaml"),
    )
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--expect-status", choices=("blocked", "verified"), required=True)
    parser.add_argument(
        "--check-artifact",
        type=Path,
        help="Verify a committed probe artifact against the computed result.",
    )
    return parser.parse_args()


def _under_root(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("probe input must be a regular file under the project root")
    return resolved


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    manifest = load_gateway_manifest(manifest_path, project_root=root)
    snapshot = None
    if args.snapshot is not None:
        snapshot_path = args.snapshot if args.snapshot.is_absolute() else root / args.snapshot
        snapshot = GatewayMetadataSnapshot.model_validate_json(
            _under_root(snapshot_path, root).read_text(encoding="utf-8")
        )
    result = probe_gateway_identity(
        manifest,
        snapshot,
        manifest_sha256=sha256_file(manifest_path),
    )
    print(result.model_dump_json(indent=2))
    if result.status != args.expect_status:
        return 1
    if args.check_artifact is not None:
        artifact_path = (
            args.check_artifact if args.check_artifact.is_absolute() else root / args.check_artifact
        )
        committed = GatewayProbeResult.model_validate_json(
            _under_root(artifact_path, root).read_text(encoding="utf-8")
        )
        if committed != result:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
