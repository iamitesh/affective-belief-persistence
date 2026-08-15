#!/usr/bin/env python3
"""Generate committed JSON Schemas from the runtime Pydantic models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from affective_belief_persistence.schemas import SCHEMA_MODELS


def rendered_schemas() -> dict[str, str]:
    return {
        filename: json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        for filename, model in SCHEMA_MODELS.items()
    }


def generate(destination: Path, *, check: bool) -> int:
    expected = rendered_schemas()
    stale: list[str] = []
    for filename, content in expected.items():
        path = destination / filename
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(filename)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    if stale:
        print("Generated schemas are stale: " + ", ".join(sorted(stale)))
        return 1
    if check:
        print(f"Verified {len(expected)} generated schemas")
    else:
        print(f"Generated {len(expected)} schemas in {destination}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--destination", type=Path, default=Path("schemas"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return generate(args.destination, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
