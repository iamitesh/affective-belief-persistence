"""Injected transport boundary used by provider-family adapters.

No concrete network client is constructed in this package.  CI and offline
replay inject deterministic transports; an authorized live pilot must inject a
separately configured client and produce a new run manifest.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Protocol

from pydantic import Field

from affective_belief_persistence.models.contracts import RunnerModel


class TransportRequest(RunnerModel):
    method: str = "POST"
    url: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, object]


class TransportResponse(RunnerModel):
    status_code: int = Field(ge=100, le=599)
    body: str
    headers: dict[str, str] = Field(default_factory=dict)


class ModelTransport(Protocol):
    is_live: bool

    def send(self, request: TransportRequest, *, timeout_seconds: float) -> TransportResponse:
        """Send one bounded request or raise the built-in ``TimeoutError``."""


class ScriptedTransport:
    """Deterministic offline transport for tests and cached smoke evidence."""

    is_live = False

    def __init__(self, outcomes: Iterable[TransportResponse | BaseException]) -> None:
        self._outcomes = deque(outcomes)
        self.requests: list[TransportRequest] = []

    def send(self, request: TransportRequest, *, timeout_seconds: float) -> TransportResponse:
        del timeout_seconds
        self.requests.append(request)
        if not self._outcomes:
            raise AssertionError("scripted transport has no remaining outcomes")
        outcome = self._outcomes.popleft()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
