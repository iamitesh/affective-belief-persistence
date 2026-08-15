"""Strict contracts for deterministic dataset generation and manifests."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from affective_belief_persistence.world import FormationCondition, WorldModel

FORMATIONS: tuple[FormationCondition, ...] = (
    "neutral_connection",
    "romantic_prompt",
    "shared_memory",
    "memory_plus_investment",
)


class DatasetConfig(WorldModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    dataset_version: str = Field(min_length=1)
    generator_version: Literal["1.0.0"]
    seed: int = Field(ge=0)
    source_commit: str = Field(min_length=7)
    freeze_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    formation_conditions: tuple[FormationCondition, ...] = Field(min_length=4, max_length=4)
    baseline_days: tuple[int, int]
    formation_days: tuple[int, int]
    reality_shock_day: int
    adaptation_days: tuple[int, int]
    smoke_days_per_condition: int = Field(ge=1, le=5)

    @model_validator(mode="after")
    def validate_freeze(self) -> DatasetConfig:
        if self.formation_conditions != FORMATIONS:
            raise ValueError("formation conditions must use the frozen order")
        if (
            self.baseline_days != (1, 5)
            or self.formation_days != (6, 25)
            or self.reality_shock_day != 26
            or self.adaptation_days != (27, 40)
        ):
            raise ValueError("dataset phases must match Gate 0")
        return self


class PartitionManifest(WorldModel):
    path: str
    role: Literal["formation", "held_out", "control", "smoke"]
    record_count: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_day: int = Field(ge=1)
    last_day: int = Field(ge=1)
    protected_from_training: bool


class DatasetManifest(WorldModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str
    dataset_version: str
    generator_id: Literal["gate1-dataset-generator"] = "gate1-dataset-generator"
    generator_version: Literal["1.0.0"] = "1.0.0"
    seed: int
    source_commit: str
    freeze_date: str
    synthetic: Literal[True] = True
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    safety_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    partitions: tuple[PartitionManifest, ...] = Field(min_length=7)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation: dict[str, Literal["passed"]]
    manual_review_sample_ids: tuple[str, ...] = Field(min_length=4)
    known_imperfections: tuple[str, ...]
