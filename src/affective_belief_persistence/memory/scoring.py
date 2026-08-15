"""Deterministic offline relevance and transparent score composition."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from affective_belief_persistence.config import load_yaml
from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.memory.contracts import (
    Memory,
    MemoryModel,
    RetrievalQuery,
    RetrievalScoreComponents,
)

_TOKEN = re.compile(r"[a-z0-9]+")
ExclusionReason: TypeAlias = Literal[
    "not_retrieval_eligible", "blocked_memory_id", "blocked_condition_tag"
]


class RetrievalWeights(MemoryModel):
    query_relevance: float = Field(ge=0, le=1)
    recency: float = Field(ge=0, le=1)
    salience: float = Field(ge=0, le=1)
    goal_relevance: float = Field(ge=0, le=1)
    participant_relevance: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> RetrievalWeights:
        if not math.isclose(sum(self.model_dump().values()), 1.0, rel_tol=0, abs_tol=1e-12):
            raise ValueError("retrieval weights must sum to exactly 1.0")
        return self


class MemoryConfig(MemoryModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_version: str = Field(min_length=1)
    top_k: int = Field(ge=1, le=20)
    recency_half_life_days: float = Field(gt=0)
    partner_salience: float = Field(ge=0, le=1)
    other_salience: float = Field(ge=0, le=1)
    score_precision: int = Field(ge=6, le=15)
    weights: RetrievalWeights

    @property
    def sha256(self) -> str:
        return sha256_value(self.model_dump(mode="json"))


def load_memory_config(path: Path) -> MemoryConfig:
    """Load strict YAML; unknown scoring knobs fail closed."""

    if not path.is_file() or path.is_symlink():
        raise ValueError(f"memory config must be an existing regular file: {path}")
    return MemoryConfig.model_validate(load_yaml(path))


class DeterministicMockRelevance:
    """Offline lexical relevance function with no model calls or hidden state."""

    @staticmethod
    def _tokens(text: str) -> frozenset[str]:
        return frozenset(_TOKEN.findall(text.casefold()))

    def score(self, query_text: str, memory: Memory) -> float:
        memory_text = " ".join(
            [
                memory.summary,
                *(fact.proposition for fact in memory.observable_facts),
                memory.interpretation.proposition if memory.interpretation else "",
            ]
        )
        query_tokens = self._tokens(query_text)
        memory_tokens = self._tokens(memory_text)
        union = query_tokens | memory_tokens
        if not union:
            return 0.0
        return len(query_tokens & memory_tokens) / len(union)


def _set_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    union = set(left) | set(right)
    if not union:
        return 0.0
    return len(set(left) & set(right)) / len(union)


def exclusion_reason(query: RetrievalQuery, memory: Memory) -> ExclusionReason | None:
    if not memory.retrieval_eligible:
        return "not_retrieval_eligible"
    if memory.memory_id in query.blocked_memory_ids:
        return "blocked_memory_id"
    if set(memory.condition_tags) & set(query.blocked_condition_tags):
        return "blocked_condition_tag"
    return None


def score_components(
    query: RetrievalQuery,
    memory: Memory,
    *,
    config: MemoryConfig,
    relevance: DeterministicMockRelevance,
) -> RetrievalScoreComponents:
    """Compute every preregisterable component on a bounded [0, 1] scale."""

    age = max(0, query.simulation_day - memory.simulation_day)
    recency = 0.5 ** (age / config.recency_half_life_days)
    eligible = exclusion_reason(query, memory) is None
    values = {
        "query_relevance": relevance.score(query.text, memory),
        "recency": recency,
        "salience": memory.salience,
        "goal_relevance": _set_overlap(query.goal_ids, memory.goal_ids),
        "participant_relevance": _set_overlap(query.participant_ids, memory.participants),
        "experimental_filter": 1.0 if eligible else 0.0,
    }
    return RetrievalScoreComponents(
        **{name: round(value, config.score_precision) for name, value in values.items()}
    )


def total_score(components: RetrievalScoreComponents, config: MemoryConfig) -> float:
    if components.experimental_filter == 0:
        return 0.0
    weighted = (
        components.query_relevance * config.weights.query_relevance
        + components.recency * config.weights.recency
        + components.salience * config.weights.salience
        + components.goal_relevance * config.weights.goal_relevance
        + components.participant_relevance * config.weights.participant_relevance
    )
    return round(weighted, config.score_precision)
