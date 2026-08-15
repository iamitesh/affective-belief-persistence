#!/usr/bin/env python3
"""Generate or verify the deterministic Gate 1 synthetic dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from affective_belief_persistence.data.generation import build_dataset, write_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    build = build_dataset(root)
    stale = write_dataset(root, build, check=args.check)
    if stale:
        print("Generated dataset files are stale: " + ", ".join(stale))
        return 1
    verb = "Verified" if args.check else "Generated"
    print(f"{verb} {len(build.files)} Gate 1 files; dataset_sha256={build.manifest.dataset_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
