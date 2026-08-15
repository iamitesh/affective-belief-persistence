"""Canonical serialization, hashing, and namespaced seed derivation."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data with a stable byte representation."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    rendered = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return unicodedata.normalize("NFC", rendered)


def sha256_value(value: Any) -> str:
    """Hash a JSON-compatible value after canonical serialization."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file without loading it completely into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_seed(root_seed: int, *namespace: str) -> int:
    """Derive an independent deterministic 64-bit seed for a component."""

    if not 0 <= root_seed <= 2**63 - 1:
        raise ValueError("root seed must be an unsigned 63-bit integer")
    payload = {
        "algorithm": "sha256-namespaced-v1",
        "root_seed": root_seed,
        "namespace": list(namespace),
    }
    return int(sha256_value(payload)[:16], 16)
