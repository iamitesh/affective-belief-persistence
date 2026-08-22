"""Rich deterministic mock and memory bridge used only for Gate 2 engineering."""

from __future__ import annotations

import random
from dataclasses import dataclass

from affective_belief_persistence.determinism import canonical_json, derive_seed, sha256_value
from affective_belief_persistence.harness.contracts import SelectedMemoryEvidence
from affective_belief_persistence.interventions.contracts import PreActionOverlay
from affective_belief_persistence.interventions.runtime import InterventionRuntime
from affective_belief_persistence.memory.integration import (
    DecisionMemoryContext,
    MemoryRuntimeCheckpoint,
    PendingMemoryCommit,
)
from affective_belief_persistence.models.cache import SafeResponseCache
from affective_belief_persistence.models.contracts import (
    ActionContext,
    BeliefContext,
    GoalContext,
    MemoryReference,
    ModelInput,
    Phase,
    ResourceContext,
)
from affective_belief_persistence.models.prompt_builder import PromptBundle
from affective_belief_persistence.schemas import DecisionRequest
from affective_belief_persistence.simulation.actions import ActionCommitment
from affective_belief_persistence.simulation.clock import phase_for_day
from affective_belief_persistence.simulation.consequences import ConsequenceApplication
from affective_belief_persistence.simulation.model import ActionSelection
from affective_belief_persistence.simulation.scenario_loader import LoadedScenario
from affective_belief_persistence.world import ActionOption, Event


class HarnessModelError(RuntimeError):
    """The rich mock cannot proceed without violating a Gate 2 binding."""


@dataclass(frozen=True)
class ModelLedgerState:
    ledger_sha256: str
    trace_count: int


@dataclass(frozen=True)
class _PendingTrace:
    request_id: str
    model_input: ModelInput
    selected_memories: tuple[SelectedMemoryEvidence, ...]
    pre_action_overlay: PreActionOverlay
    action_prompt_sha256: str
    action_cache_key: str
    ledger_after_action_sha256: str


@dataclass(frozen=True)
class StepModelTrace:
    request_id: str
    model_input: ModelInput
    selected_memories: tuple[SelectedMemoryEvidence, ...]
    pre_action_overlay: PreActionOverlay
    action_prompt_sha256: str
    action_cache_key: str
    public_language_prompt_sha256: str
    public_language_cache_key: str
    model_ledger_sha256: str


class HarnessMemoryBridge:
    """Capture the exact pre-action context while delegating all durable memory work."""

    def __init__(self, runtime: InterventionRuntime) -> None:
        self.runtime = runtime
        self.latest_event: Event | None = None
        self.latest_context: DecisionMemoryContext | None = None
        self.latest_overlay: PreActionOverlay | None = None

    def context_for_action(
        self,
        *,
        event: Event,
        goal_ids: tuple[str, ...],
        seed: int,
    ) -> DecisionMemoryContext:
        context = self.runtime.context_for_action(event=event, goal_ids=goal_ids, seed=seed)
        self.latest_event = event
        self.latest_context = context
        self.latest_overlay = self.runtime.pre_action_overlay(day=event.day)
        return context

    def stage_after_consequence(
        self,
        *,
        event: Event,
        action: ActionOption,
        commitment: ActionCommitment,
        consequence: ConsequenceApplication,
        decision_context: DecisionMemoryContext,
    ) -> PendingMemoryCommit:
        return self.runtime.stage_after_consequence(
            event=event,
            action=action,
            commitment=commitment,
            consequence=consequence,
            decision_context=decision_context,
        )

    def commit_after_step(self, pending: PendingMemoryCommit, *, source_record_sha256: str) -> None:
        self.runtime.commit_after_step(pending, source_record_sha256=source_record_sha256)

    def checkpoint(self) -> MemoryRuntimeCheckpoint:
        return self.runtime.memory.checkpoint()

    def fresh(self) -> HarnessMemoryBridge:
        return HarnessMemoryBridge(self.runtime.fresh())

    def replace_runtime(self, runtime: InterventionRuntime) -> None:
        self.runtime = runtime
        self.latest_event = None
        self.latest_context = None
        self.latest_overlay = None


def _selected_memory_evidence(
    runtime: InterventionRuntime,
    memory_ids: tuple[str, ...],
) -> tuple[SelectedMemoryEvidence, ...]:
    selected: list[SelectedMemoryEvidence] = []
    for memory_id in memory_ids:
        # Day 30 may be executing against Issue 11's transactional clone. This
        # public accessor exposes that immutable pre-action view without
        # committing it or reaching into private pending state.
        memory = runtime.get_pre_action_memory(memory_id)
        interpretation = memory.interpretation
        source_ids = tuple(
            dict.fromkeys(
                (
                    memory.source_event_id,
                    memory.provenance.source_candidate_id,
                    *(fact.fact_id for fact in memory.observable_facts),
                )
            )
        )
        selected.append(
            SelectedMemoryEvidence.create(
                memory_id=memory.memory_id,
                summary=memory.summary,
                observable_facts=tuple(
                    fact.proposition for fact in memory.observable_facts if fact.truth
                ),
                active_interpretation=(
                    interpretation.proposition if interpretation is not None else None
                ),
                active_interpretation_id=(
                    interpretation.interpretation_id if interpretation is not None else None
                ),
                active_interpretation_revision=(
                    interpretation.revision if interpretation is not None else None
                ),
                source_ids=source_ids,
            )
        )
    return tuple(selected)


def _belief_context(runtime: InterventionRuntime) -> tuple[BeliefContext, ...]:
    belief = runtime.memory.beliefs.current(f"belief-{runtime.memory.relationship_id}")
    if belief is None:
        return ()
    evidence_ids = (*belief.supporting_evidence_ids, *belief.contradicting_evidence_ids)
    values: tuple[tuple[str, bool | float | str], ...] = (
        (
            "relationship-active",
            belief.relationship_active if belief.relationship_active is not None else "unknown",
        ),
        (
            "relationship-romantic",
            belief.relationship_romantic if belief.relationship_romantic is not None else "unknown",
        ),
        (
            "relationship-reciprocal",
            belief.relationship_reciprocal
            if belief.relationship_reciprocal is not None
            else "unknown",
        ),
        ("partner-reliability", belief.partner_reliability),
        ("expected-future-interaction", belief.expected_future_interaction),
    )
    return tuple(
        BeliefContext(
            belief_id=belief_id,
            value=value,
            confidence=belief.confidence,
            evidence_ids=evidence_ids,
        )
        for belief_id, value in values
    )


class Gate2DeterministicModel:
    """Use Issue #12's rich ModelInput while making zero provider calls."""

    model_id = "deterministic-mock"
    revision = "mock-v1"

    def __init__(
        self,
        *,
        scenario: LoadedScenario,
        bridge: HarnessMemoryBridge,
        prompts: PromptBundle,
        model_config_sha256: str,
        initial_ledger_sha256: str | None = None,
    ) -> None:
        if scenario.model_settings.model_id != self.model_id:
            raise HarnessModelError("Gate 2 mock model ID differs from the scenario")
        if scenario.model_settings.revision != self.revision:
            raise HarnessModelError("Gate 2 mock revision differs from the scenario")
        self.scenario = scenario
        self.bridge = bridge
        self.prompts = prompts
        self.model_config_sha256 = model_config_sha256
        self._ledger_sha256 = initial_ledger_sha256 or sha256_value(
            {"cell_base": self._base_run_id(), "ledger": "gate2-model-ledger-v1"}
        )
        self._pending: dict[str, _PendingTrace] = {}
        self._traces: list[StepModelTrace] = []

    @property
    def ledger_sha256(self) -> str:
        return self._ledger_sha256

    def state(self) -> ModelLedgerState:
        return ModelLedgerState(
            ledger_sha256=self._ledger_sha256,
            trace_count=len(self._traces),
        )

    def restore_state(self, state: ModelLedgerState) -> None:
        if state.trace_count > len(self._traces):
            raise HarnessModelError("cannot restore a future model ledger state")
        self._ledger_sha256 = state.ledger_sha256
        self._traces = self._traces[: state.trace_count]
        self._pending.clear()

    def trace_for_request(self, request_id: str) -> StepModelTrace:
        matches = [trace for trace in self._traces if trace.request_id == request_id]
        if len(matches) != 1:
            raise HarnessModelError("model trace is missing or duplicated")
        return matches[0]

    def _base_run_id(self) -> str:
        # Deliberately excludes intervention assignment. Matched arms must have
        # identical pre-day-30 inputs within each formation.
        return sha256_value(
            {
                "contract": "gate2-rich-deterministic-mock-v1",
                "dataset_sha256": self.scenario.manifest.dataset_sha256,
                "formation_condition": self.scenario.config.formation_condition,
                "model_config_sha256": self.model_config_sha256,
                "scenario_sha256": self.scenario.scenario_sha256,
                "seed": self.scenario.config.seed,
            }
        )

    def _rich_input(
        self,
        request: DecisionRequest,
    ) -> tuple[ModelInput, tuple[SelectedMemoryEvidence, ...]]:
        event = self.bridge.latest_event
        context = self.bridge.latest_context
        overlay = self.bridge.latest_overlay
        if event is None or context is None or overlay is None:
            raise HarnessModelError("memory retrieval and intervention overlay must precede action")
        if event.event_id != request.event_id or event.day != request.day:
            raise HarnessModelError("model request differs from the captured pre-action event")
        if tuple(request.retrieved_memory_ids) != context.retrieved_memory_ids:
            raise HarnessModelError("model request omits or reorders selected memories")
        selected = _selected_memory_evidence(
            self.bridge.runtime,
            context.retrieved_memory_ids,
        )
        selected_by_id = {item.memory_id: item for item in selected}
        memory_references = tuple(
            MemoryReference(
                memory_id=memory_id,
                content=canonical_json(selected_by_id[memory_id].content_payload()),
                source_ids=selected_by_id[memory_id].source_ids,
            )
            for memory_id in context.retrieved_memory_ids
        )
        goal_ids = tuple(
            sorted(
                {
                    goal_id
                    for action_id in event.available_action_ids
                    for goal_id in next(
                        item for item in self.scenario.actions if item.action_id == action_id
                    ).goal_ids
                }
            )
        )
        base = ModelInput(
            run_id=self._base_run_id(),
            request_id=request.request_id,
            event_id=request.event_id,
            day=request.day,
            phase=Phase(phase_for_day(request.day)),
            observable_facts=tuple(request.facts),
            current_goals=tuple(
                GoalContext(goal_id=goal_id, description=goal_id) for goal_id in goal_ids
            ),
            resources=ResourceContext(available=request.action_points),
            allowed_actions=tuple(
                ActionContext(
                    action_id=action.action_id,
                    description=action.description,
                    cost=action.cost,
                )
                for action in request.available_actions
            ),
            retrieved_memories=memory_references,
            current_beliefs=_belief_context(self.bridge.runtime),
            active_intervention=None,
            prompt_version=self.prompts.version,
        )
        enriched = self.bridge.runtime.overlay_model_input(base)
        if self.bridge.runtime.pre_action_overlay(day=request.day) != overlay:
            raise HarnessModelError("pre-action overlay changed during input materialization")
        return enriched, selected

    def select_action(self, request: DecisionRequest, *, seed: int) -> ActionSelection:
        model_input, selected_memories = self._rich_input(request)
        prompt = self.prompts.render_action(model_input)
        input_sha256 = sha256_value(model_input)
        cache_key = SafeResponseCache.make_key(
            {
                "config_sha256": self.model_config_sha256,
                "input_sha256": input_sha256,
                "prompt_sha256": prompt.sha256,
                "seed": seed,
                "stage": "action",
            }
        )
        ordered = tuple(sorted(request.available_actions, key=lambda item: item.action_id))
        decision_seed = derive_seed(seed, self.model_id, self.revision, input_sha256)
        selected = ordered[random.Random(decision_seed).randrange(len(ordered))]
        decision_id = sha256_value(
            {
                "chosen_action_id": selected.action_id,
                "input_sha256": input_sha256,
                "model_config_sha256": self.model_config_sha256,
                "seed": decision_seed,
            }
        )
        selection = ActionSelection(
            decision_id=decision_id,
            chosen_action=selected.action_id,
            resources_spent=selected.cost,
            retrieved_memory_ids=tuple(item.memory_id for item in selected_memories),
            belief_updates=(),
        )
        ledger_after_action = sha256_value(
            {
                "cache_key": cache_key,
                "input_sha256": input_sha256,
                "previous_model_ledger_sha256": self._ledger_sha256,
                "prompt_sha256": prompt.sha256,
                "selection": selection.model_dump(mode="json"),
                "stage": "action",
            }
        )
        overlay = self.bridge.latest_overlay
        if overlay is None:
            raise HarnessModelError("pre-action overlay disappeared before action selection")
        self._pending[selection.decision_id] = _PendingTrace(
            request_id=request.request_id,
            model_input=model_input,
            selected_memories=selected_memories,
            pre_action_overlay=overlay,
            action_prompt_sha256=prompt.sha256,
            action_cache_key=cache_key,
            ledger_after_action_sha256=ledger_after_action,
        )
        self._ledger_sha256 = ledger_after_action
        return selection

    def generate_public_language(
        self,
        request: DecisionRequest,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        try:
            pending = self._pending.pop(selection.decision_id)
        except KeyError as exc:
            raise HarnessModelError("public language lacks a committed action-stage trace") from exc
        if pending.request_id != request.request_id:
            raise HarnessModelError("public-language request differs from action-stage input")
        prompt = self.prompts.render_language(
            pending.model_input,
            chosen_action_id=selection.chosen_action,
            action_commitment_sha256=action_commitment_sha256,
        )
        cache_key = SafeResponseCache.make_key(
            {
                "action_commitment_sha256": action_commitment_sha256,
                "config_sha256": self.model_config_sha256,
                "input_sha256": sha256_value(pending.model_input),
                "prompt_sha256": prompt.sha256,
                "seed": seed,
                "stage": "public_language",
            }
        )
        self._ledger_sha256 = sha256_value(
            {
                "action_commitment_sha256": action_commitment_sha256,
                "cache_key": cache_key,
                "previous_model_ledger_sha256": pending.ledger_after_action_sha256,
                "prompt_sha256": prompt.sha256,
                "stage": "public_language",
            }
        )
        self._traces.append(
            StepModelTrace(
                request_id=request.request_id,
                model_input=pending.model_input,
                selected_memories=pending.selected_memories,
                pre_action_overlay=pending.pre_action_overlay,
                action_prompt_sha256=pending.action_prompt_sha256,
                action_cache_key=pending.action_cache_key,
                public_language_prompt_sha256=prompt.sha256,
                public_language_cache_key=cache_key,
                model_ledger_sha256=self._ledger_sha256,
            )
        )
        return f"Mock decision: {selection.chosen_action}."
