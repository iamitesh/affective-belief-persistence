"""Content-addressed model-response cache with explicit retention policy."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from pydantic import Field

from affective_belief_persistence.determinism import canonical_json, sha256_value
from affective_belief_persistence.models.contracts import RunnerModel
from affective_belief_persistence.models.errors import CacheCorruptionError


class ResponseRetentionPolicy(Protocol):
    def allow_raw_response(self, response: str) -> bool:
        """Return true only after the response passes the applicable safety scan."""


class HashOnlyRetentionPolicy:
    """Safe default: preserve only a response hash in invocation evidence."""

    def allow_raw_response(self, response: str) -> bool:
        del response
        return False


class SyntheticFixtureRetentionPolicy:
    """Explicit opt-in used only for non-sensitive, deterministic fixtures."""

    def allow_raw_response(self, response: str) -> bool:
        # Test fixtures are still rejected if they resemble obvious secrets or
        # private-reasoning blocks. Production callers should inject the full
        # repository SafetyEvaluator instead of this narrow fixture policy.
        lowered = response.casefold()
        blocked = (
            "begin private reasoning",
            "private scratchpad:",
            "authorization: bearer",
            "api_key",
            "api-key",
        )
        return not any(marker in lowered for marker in blocked)


class CachedResponse(RunnerModel):
    schema_version: str = "1.0"
    cache_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    status_code: int = Field(ge=200, le=299)
    body: str
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SafeResponseCache:
    """Filesystem cache that never stores headers, credentials, or unsafe raw text."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def make_key(parts: object) -> str:
        return sha256_value({"cache_contract": "model-response-v1", "parts": parts})

    def _path(self, key: str) -> Path:
        if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
            raise ValueError("cache key must be a lowercase SHA-256 digest")
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> CachedResponse | None:
        path = self._path(key)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise CacheCorruptionError(f"cache entry is not a regular file: {path}")
        try:
            cached = CachedResponse.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CacheCorruptionError(f"invalid cache entry {path}: {exc}") from exc
        if cached.cache_key != key or cached.body_sha256 != sha256_value(cached.body):
            raise CacheCorruptionError(f"cache entry failed hash validation: {path}")
        return cached

    def put(
        self,
        key: str,
        *,
        status_code: int,
        body: str,
        retention_policy: ResponseRetentionPolicy,
    ) -> bool:
        """Store a successful response only when policy explicitly permits raw retention."""

        if not 200 <= status_code <= 299:
            return False
        if not retention_policy.allow_raw_response(body):
            return False
        path = self._path(key)
        if path.exists() and path.is_symlink():
            raise CacheCorruptionError(f"cache entry cannot be a symlink: {path}")
        if path.exists():
            existing = self.get(key)
            if existing is None or existing.body != body or existing.status_code != status_code:
                raise CacheCorruptionError(
                    "immutable cache key already maps to different response content"
                )
            return True
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise CacheCorruptionError(f"cache directory cannot be a symlink: {path.parent}")
        cached = CachedResponse(
            cache_key=key,
            status_code=status_code,
            body=body,
            body_sha256=sha256_value(body),
        )
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_text(canonical_json(cached) + "\n", encoding="utf-8", newline="\n")
            os.replace(temporary, path)
        except OSError as exc:
            raise CacheCorruptionError(
                f"could not atomically write cache entry {path}: {exc}"
            ) from exc
        return True
