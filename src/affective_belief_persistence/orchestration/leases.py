"""Deterministic repository path leases with bounded worker concurrency."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Literal

from affective_belief_persistence.orchestration.registry import normalize_repository_path

LeaseAccess = Literal["read", "write"]
ReleaseResult = Literal["completed", "failed", "cancelled", "expired"]


class LeaseError(RuntimeError):
    """Base error for lease lifecycle violations."""


class LeaseConflictError(LeaseError):
    """A requested scope overlaps an incompatible active lease."""


class LeaseCapacityError(LeaseError):
    """Granting a lease would exceed the three-worker safety limit."""


class LeaseNotFoundError(LeaseError):
    """No active lease matches the supplied lease or task identifier."""


class LeaseOwnershipError(LeaseError):
    """A lease lifecycle operation was attempted by a different agent."""


@dataclass(frozen=True)
class PathLease:
    """An active task lease over canonical repository scopes."""

    lease_id: str
    task_id: str
    agent_id: str
    path_patterns: tuple[str, ...]
    access: LeaseAccess
    granted_at: datetime
    expires_at: datetime
    heartbeat_at: datetime
    shared_integration: bool = False

    @property
    def paths(self) -> tuple[str, ...]:
        """Compatibility alias for schedulers that call scopes ``paths``."""

        return self.path_patterns

    def is_expired(self, at: datetime) -> bool:
        return at >= self.expires_at


@dataclass(frozen=True)
class LeaseRelease:
    """Audit record returned when a lease leaves the active set."""

    lease: PathLease
    released_at: datetime
    result: ReleaseResult


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LeaseError("lease timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _normalize_scope(path_pattern: str) -> str:
    candidate = path_pattern.strip().rstrip("/")
    subtree = candidate.endswith("/**")
    prefix = candidate[:-3] if subtree else candidate
    if any(character in prefix for character in "*?[]"):
        raise LeaseError(f"lease paths support wildcards only as a terminal '/**': {path_pattern}")
    try:
        normalized = normalize_repository_path(prefix)
    except ValueError as exc:
        raise LeaseError(f"invalid lease path '{path_pattern}': {exc}") from exc
    return f"{normalized}/**" if subtree else normalized


def _scope_prefix(scope: str) -> tuple[str, ...]:
    concrete = scope[:-3] if scope.endswith("/**") else scope
    return tuple(concrete.split("/"))


def paths_overlap(left: str, right: str) -> bool:
    """Return whether two exact/subtree scopes overlap, independent of call order."""

    left_scope = _normalize_scope(left)
    right_scope = _normalize_scope(right)
    left_parts = _scope_prefix(left_scope)
    right_parts = _scope_prefix(right_scope)
    common_length = min(len(left_parts), len(right_parts))
    if left_parts[:common_length] != right_parts[:common_length]:
        return False
    if len(left_parts) == len(right_parts):
        return True
    if len(left_parts) < len(right_parts):
        return left_scope.endswith("/**")
    return right_scope.endswith("/**")


def _canonical_scopes(paths: Iterable[str]) -> tuple[str, ...]:
    normalized = sorted({_normalize_scope(path) for path in paths})
    if not normalized:
        raise LeaseError("a lease must contain at least one path")
    # A parent subtree already covers nested scopes; dropping them makes conflict
    # reporting stable even when callers provide redundant paths in different orders.
    result: list[str] = []
    for scope in normalized:
        if any(parent.endswith("/**") and paths_overlap(parent, scope) for parent in result):
            continue
        result.append(scope)
    return tuple(result)


class PathLeaseManager:
    """In-memory lease authority used by the supervisor and persisted by state code."""

    def __init__(
        self,
        *,
        max_workers: int = 3,
        default_ttl_seconds: int = 900,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not 1 <= max_workers <= 3:
            raise LeaseCapacityError("max_workers must be between one and three")
        if default_ttl_seconds < 1:
            raise LeaseError("default_ttl_seconds must be positive")
        self.max_workers = max_workers
        self.default_ttl_seconds = default_ttl_seconds
        self._clock = clock
        self._leases: dict[str, PathLease] = {}
        self._sequence = 0

    def _now(self, at: datetime | None = None) -> datetime:
        return _aware_utc(at or self._clock())

    def expire(self, *, at: datetime | None = None) -> tuple[LeaseRelease, ...]:
        """Expire stale leases in stable identifier order and return audit records."""

        now = self._now(at)
        expired = [lease for lease in self._leases.values() if lease.is_expired(now)]
        releases = []
        for lease in sorted(expired, key=lambda item: item.lease_id):
            del self._leases[lease.lease_id]
            releases.append(LeaseRelease(lease=lease, released_at=now, result="expired"))
        return tuple(releases)

    def active_leases(self, *, at: datetime | None = None) -> tuple[PathLease, ...]:
        self.expire(at=at)
        return tuple(sorted(self._leases.values(), key=lambda lease: lease.lease_id))

    @property
    def active_worker_count(self) -> int:
        self.expire()
        return len({lease.agent_id for lease in self._leases.values()})

    def _make_lease_id(
        self, task_id: str, agent_id: str, scopes: tuple[str, ...], granted_at: datetime
    ) -> str:
        self._sequence += 1
        payload = "|".join(
            (task_id, agent_id, *scopes, granted_at.isoformat(), str(self._sequence))
        )
        return f"lease-{sha256(payload.encode('utf-8')).hexdigest()[:16]}"

    def acquire(
        self,
        task_id: str,
        paths: Iterable[str],
        *,
        agent_id: str | None = None,
        access: LeaseAccess = "write",
        ttl_seconds: int | None = None,
        shared_integration: bool = False,
        at: datetime | None = None,
    ) -> PathLease:
        """Grant a lease or raise a typed conflict/capacity error.

        ``agent_id`` may be omitted by a simple scheduler, in which case the task is
        treated as its own worker identity. Shared writes are only compatible when
        both leases were explicitly marked as supervisor-created integration work.
        """

        if not task_id.strip():
            raise LeaseError("task_id cannot be empty")
        owner = (agent_id or task_id).strip()
        if not owner:
            raise LeaseError("agent_id cannot be empty")
        if access not in {"read", "write"}:
            raise LeaseError(f"unsupported lease access: {access}")
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        if ttl < 1:
            raise LeaseError("ttl_seconds must be positive")
        now = self._now(at)
        self.expire(at=now)
        scopes = _canonical_scopes(paths)

        active_agents = {lease.agent_id for lease in self._leases.values()}
        if owner not in active_agents and len(active_agents) >= self.max_workers:
            raise LeaseCapacityError(
                f"cannot activate '{owner}': {self.max_workers}-worker limit reached"
            )

        for existing in sorted(self._leases.values(), key=lambda lease: lease.lease_id):
            if existing.agent_id == owner:
                continue
            if existing.access == "read" and access == "read":
                continue
            if shared_integration and existing.shared_integration:
                continue
            overlap = next(
                (
                    (requested, held)
                    for requested in scopes
                    for held in existing.path_patterns
                    if paths_overlap(requested, held)
                ),
                None,
            )
            if overlap is not None:
                requested, held = overlap
                raise LeaseConflictError(
                    f"task '{task_id}' path '{requested}' conflicts with "
                    f"task '{existing.task_id}' path '{held}'"
                )

        lease = PathLease(
            lease_id=self._make_lease_id(task_id, owner, scopes, now),
            task_id=task_id,
            agent_id=owner,
            path_patterns=scopes,
            access=access,
            granted_at=now,
            expires_at=now + timedelta(seconds=ttl),
            heartbeat_at=now,
            shared_integration=shared_integration,
        )
        self._leases[lease.lease_id] = lease
        return lease

    def heartbeat(
        self,
        lease_id: str,
        *,
        agent_id: str | None = None,
        ttl_seconds: int | None = None,
        at: datetime | None = None,
    ) -> PathLease:
        """Renew a live lease from the heartbeat time."""

        now = self._now(at)
        self.expire(at=now)
        lease = self._leases.get(lease_id)
        if lease is None:
            raise LeaseNotFoundError(f"active lease not found: {lease_id}")
        if agent_id is not None and lease.agent_id != agent_id:
            raise LeaseOwnershipError(f"agent '{agent_id}' does not own lease '{lease_id}'")
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        if ttl < 1:
            raise LeaseError("ttl_seconds must be positive")
        renewed = replace(
            lease,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        self._leases[lease_id] = renewed
        return renewed

    def release(
        self,
        task_or_lease_id: str,
        *,
        agent_id: str | None = None,
        result: ReleaseResult = "completed",
        at: datetime | None = None,
    ) -> tuple[LeaseRelease, ...]:
        """Release one lease ID or every lease associated with a task ID."""

        if result not in {"completed", "failed", "cancelled", "expired"}:
            raise LeaseError(f"unsupported release result: {result}")
        now = self._now(at)
        self.expire(at=now)
        matches = [
            lease
            for lease in self._leases.values()
            if lease.lease_id == task_or_lease_id or lease.task_id == task_or_lease_id
        ]
        if not matches:
            raise LeaseNotFoundError(f"active lease or task not found: {task_or_lease_id}")
        if agent_id is not None:
            mismatched = [lease.lease_id for lease in matches if lease.agent_id != agent_id]
            if mismatched:
                raise LeaseOwnershipError(
                    f"agent '{agent_id}' does not own lease(s): {', '.join(sorted(mismatched))}"
                )
        releases = []
        for lease in sorted(matches, key=lambda item: item.lease_id):
            del self._leases[lease.lease_id]
            releases.append(LeaseRelease(lease=lease, released_at=now, result=result))
        return tuple(releases)


# Short alias for callers that model the component rather than its storage strategy.
LeaseManager = PathLeaseManager
