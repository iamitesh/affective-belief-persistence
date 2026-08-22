"""Lazy public API for the auditable memory and belief subsystem.

Imports remain lazy because the root schema registry imports
``memory.contracts.MEMORY_SCHEMA_MODELS`` during its own initialization.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MEMORY_SCHEMA_MODELS": ("contracts", "MEMORY_SCHEMA_MODELS"),
    "Belief": ("contracts", "Belief"),
    "BeliefCheckpoint": ("beliefs", "BeliefCheckpoint"),
    "BeliefError": ("beliefs", "BeliefError"),
    "BeliefLedger": ("beliefs", "BeliefLedger"),
    "BeliefProposal": ("update", "BeliefProposal"),
    "DecisionMemoryContext": ("integration", "DecisionMemoryContext"),
    "DeterministicMockRelevance": ("scoring", "DeterministicMockRelevance"),
    "EpisodeStore": ("store", "EpisodeStore"),
    "Memory": ("contracts", "Memory"),
    "MemoryConfig": ("scoring", "MemoryConfig"),
    "MemoryIntegration": ("integration", "MemoryIntegration"),
    "MemoryInterpretation": ("contracts", "MemoryInterpretation"),
    "MemoryRuntime": ("integration", "MemoryRuntime"),
    "MemoryRuntimeCheckpoint": ("integration", "MemoryRuntimeCheckpoint"),
    "MemoryStoreCheckpoint": ("store", "MemoryStoreCheckpoint"),
    "MemoryStoreError": ("store", "MemoryStoreError"),
    "NullMemoryIntegration": ("integration", "NullMemoryIntegration"),
    "PendingMemoryCommit": ("integration", "PendingMemoryCommit"),
    "RetrievalCandidateScore": ("contracts", "RetrievalCandidateScore"),
    "RetrievalEngine": ("retrieval", "RetrievalEngine"),
    "RetrievalError": ("retrieval", "RetrievalError"),
    "RetrievalQuery": ("contracts", "RetrievalQuery"),
    "RetrievalRecord": ("contracts", "RetrievalRecord"),
    "RetrievalScoreComponents": ("contracts", "RetrievalScoreComponents"),
    "RetrievalWeights": ("scoring", "RetrievalWeights"),
    "accept_validated_proposal": ("update", "accept_validated_proposal"),
    "create_query": ("retrieval", "create_query"),
    "initial_belief": ("update", "initial_belief"),
    "load_memory_config": ("scoring", "load_memory_config"),
    "update_belief_evidence": ("update", "update_belief_evidence"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(
        import_module(f"affective_belief_persistence.memory.{module_name}"),
        attribute,
    )
    globals()[name] = value
    return value
