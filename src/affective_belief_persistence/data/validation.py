"""Gate 1 validation for matching, leakage, privacy, and resources."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from affective_belief_persistence.safety import SafetyEvaluator, TextContext
from affective_belief_persistence.world import (
    ActionOption,
    Consequence,
    Event,
    FormationCondition,
    ResourceBudget,
)

FORMATIONS: frozenset[FormationCondition] = frozenset(
    {
        "neutral_connection",
        "romantic_prompt",
        "shared_memory",
        "memory_plus_investment",
    }
)
PROTECTED_PHRASES = (
    "breakup",
    "broke up",
    "rejection",
    "non reciprocity",
    "relationship loss",
    "post separation recovery",
    "memory blocking",
    "memory reframing",
    "desired post shock answer",
)


@dataclass(frozen=True)
class LeakageFinding:
    event_id: str
    detector: str
    rule: str


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def scan_formation_leakage(
    events: tuple[Event, ...], evaluator: SafetyEvaluator
) -> tuple[LeakageFinding, ...]:
    """Run exact policy, lexical/fuzzy, and concept-pair leakage screens."""

    findings: list[LeakageFinding] = []
    normalized_phrases = tuple(_normalized(phrase) for phrase in PROTECTED_PHRASES)
    for event in events:
        text = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        normalized = _normalized(text)
        for finding in evaluator.evaluate_text(text, context=TextContext.PROTECTED_TRAINING):
            findings.append(LeakageFinding(event.event_id, "policy_exact", finding.condition_id))
        for phrase in normalized_phrases:
            if phrase in normalized:
                findings.append(LeakageFinding(event.event_id, "lexical", phrase))
                continue
            window_size = len(phrase.split())
            tokens = normalized.split()
            for index in range(max(0, len(tokens) - window_size + 1)):
                window = " ".join(tokens[index : index + window_size])
                if SequenceMatcher(None, window, phrase).ratio() >= 0.92:
                    findings.append(LeakageFinding(event.event_id, "fuzzy", phrase))
                    break
        token_set = set(normalized.split())
        semantic_rules = {
            "relationship_end": ({"relationship"}, {"end", "loss", "reject", "rejection"}),
            "memory_intervention": ({"memory"}, {"block", "blocking", "reframe", "reframing"}),
            "taught_recovery": ({"post", "shock"}, {"answer", "recover", "recovery"}),
        }
        for rule, (left, right) in semantic_rules.items():
            if left.issubset(token_set) and token_set.intersection(right):
                findings.append(LeakageFinding(event.event_id, "semantic_rule", rule))
    return tuple(dict.fromkeys(findings))


def scan_privacy_and_secrets(
    events: tuple[Event, ...], evaluator: SafetyEvaluator
) -> tuple[LeakageFinding, ...]:
    findings: list[LeakageFinding] = []
    for event in events:
        text = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        for finding in evaluator.evaluate_text(text, context=TextContext.SYNTHETIC_DATA):
            if finding.condition_id in {"private_or_identifiable_data", "credential_or_secret"}:
                findings.append(
                    LeakageFinding(event.event_id, "safety_policy", finding.condition_id)
                )
    return tuple(findings)


def matching_errors(events: tuple[Event, ...]) -> tuple[str, ...]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.matching_group_id].append(event)
    errors: list[str] = []
    for group_id, members in sorted(grouped.items()):
        conditions = {item.condition_variant.formation_condition for item in members}
        if len(members) != 4 or conditions != FORMATIONS:
            errors.append(f"{group_id}: incomplete formation-condition group")
            continue
        signatures = {
            (
                item.day,
                item.phase,
                item.participant_ids,
                tuple(fact.proposition for fact in item.observable_facts),
                item.available_action_ids,
                item.consequence_ids,
                item.resource_budget_id,
                item.background_fact_ids,
            )
            for item in members
        }
        if len(signatures) != 1:
            errors.append(f"{group_id}: a non-treatment field differs")
    return tuple(errors)


def resource_errors(
    actions: tuple[ActionOption, ...],
    consequences: tuple[Consequence, ...],
    budgets: tuple[ResourceBudget, ...],
) -> tuple[str, ...]:
    consequence_by_id = {item.consequence_id: item for item in consequences}
    maximum_budget = max(item.daily_total for item in budgets)
    errors: list[str] = []
    for action in actions:
        if action.cost > maximum_budget:
            errors.append(f"{action.action_id}: cost exceeds daily budget")
        consequence = consequence_by_id[action.consequence_id]
        if consequence.resource_delta != -action.cost:
            errors.append(f"{action.action_id}: consequence does not conserve resources")
    return tuple(errors)


def identifier_errors(partitions: dict[str, tuple[Event, ...]]) -> tuple[str, ...]:
    event_ids: list[str] = []
    for events in partitions.values():
        event_ids.extend(event.event_id for event in events)
    duplicates = sorted({event_id for event_id in event_ids if event_ids.count(event_id) > 1})
    return tuple(f"duplicate event ID: {event_id}" for event_id in duplicates)
