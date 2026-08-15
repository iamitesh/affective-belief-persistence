"""Deterministic simulated time for the frozen forty-day protocol."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SimulationPhase = Literal["baseline", "formation", "reality_shock", "adaptation"]

FIRST_DAY = 1
LAST_DAY = 40
COMPLETED_DAY = 41


def phase_for_day(day: int) -> SimulationPhase:
    """Return the Gate 0 phase for a one-based simulated day."""

    if not FIRST_DAY <= day <= LAST_DAY:
        raise ValueError(f"simulation day must be in [{FIRST_DAY}, {LAST_DAY}]")
    if day <= 5:
        return "baseline"
    if day <= 25:
        return "formation"
    if day == 26:
        return "reality_shock"
    return "adaptation"


class SimulationClock(BaseModel):
    """Immutable cursor pointing to the next unfinished simulated day."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    next_day: int = Field(default=FIRST_DAY, ge=FIRST_DAY, le=COMPLETED_DAY)

    @property
    def complete(self) -> bool:
        return self.next_day == COMPLETED_DAY

    @property
    def phase(self) -> SimulationPhase | None:
        return None if self.complete else phase_for_day(self.next_day)

    def advance(self) -> SimulationClock:
        if self.complete:
            raise ValueError("cannot advance a completed simulation clock")
        return SimulationClock(next_day=self.next_day + 1)
