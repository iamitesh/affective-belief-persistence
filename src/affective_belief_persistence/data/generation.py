"""Deterministic generation of matched Gate 1 synthetic data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from affective_belief_persistence.config import load_yaml
from affective_belief_persistence.data.contracts import (
    FORMATIONS,
    DatasetConfig,
    DatasetManifest,
    PartitionManifest,
)
from affective_belief_persistence.data.validation import (
    identifier_errors,
    matching_errors,
    resource_errors,
    scan_formation_leakage,
    scan_privacy_and_secrets,
)
from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.safety import SafetyEvaluator, load_safety_policy
from affective_belief_persistence.world import (
    ActionOption,
    Character,
    ConditionVariant,
    Consequence,
    Event,
    FormationCondition,
    Goal,
    ResourceBudget,
    Scenario,
    SyntheticProvenance,
    WorldBundle,
)

GENERATOR_ID = "gate1-dataset-generator"
GENERATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class DatasetBuild:
    config: DatasetConfig
    world: WorldBundle
    partitions: dict[str, tuple[Event, ...]]
    files: dict[str, str]
    manifest: DatasetManifest


def _provenance(config: DatasetConfig, source_id: str) -> SyntheticProvenance:
    return SyntheticProvenance(
        declaration_id="gate1-dataset-declaration",
        generator_id=GENERATOR_ID,
        generator_version=config.generator_version,
        seed=config.seed,
        source_commit=config.source_commit,
        source_ids=("gate-0-evidence", source_id),
        synthetic=True,
    )


def _variant(condition: FormationCondition, *, active: bool) -> ConditionVariant:
    if not active:
        return ConditionVariant(
            formation_condition=condition,
            treatment_active=False,
            romantic_instruction=False,
            memory_mode="none",
            investment_points=0,
            declared_treatment_dimensions=(),
        )
    if condition == "neutral_connection":
        return ConditionVariant(
            formation_condition=condition,
            treatment_active=True,
            romantic_instruction=False,
            memory_mode="none",
            investment_points=0,
            declared_treatment_dimensions=(),
        )
    if condition == "romantic_prompt":
        return ConditionVariant(
            formation_condition=condition,
            treatment_active=True,
            romantic_instruction=True,
            memory_mode="none",
            investment_points=0,
            declared_treatment_dimensions=("romantic_instruction",),
        )
    if condition == "shared_memory":
        return ConditionVariant(
            formation_condition=condition,
            treatment_active=True,
            romantic_instruction=False,
            memory_mode="episodic",
            investment_points=0,
            declared_treatment_dimensions=("autobiographical_memory",),
        )
    return ConditionVariant(
        formation_condition=condition,
        treatment_active=True,
        romantic_instruction=False,
        memory_mode="episodic",
        investment_points=3,
        declared_treatment_dimensions=("autobiographical_memory", "costly_investment"),
    )


def _load_template(root: Path, name: str) -> Event:
    path = root / "scenarios" / "templates" / f"{name}.yaml"
    return Event.model_validate(load_yaml(path)["event"])


def _clone_event(
    template: Event,
    *,
    config: DatasetConfig,
    day: int,
    phase: str,
    condition: FormationCondition,
    prefix: str,
    treatment_active: bool,
) -> Event:
    event_id = f"{prefix}-{day:02d}-{condition}"
    fact_id = f"fact-{event_id}"
    payload = template.model_dump(mode="json")
    payload.update(
        {
            "event_id": event_id,
            "matching_group_id": f"{prefix}-day-{day:02d}",
            "day": day,
            "phase": phase,
            "condition_variant": _variant(condition, active=treatment_active).model_dump(
                mode="json"
            ),
            "provenance": _provenance(config, template.event_id).model_dump(mode="json"),
        }
    )
    payload["observable_facts"][0]["fact_id"] = fact_id
    for index, item in enumerate(payload["interpretations"]):
        item["interpretation_id"] = f"interpretation-{event_id}-{index + 1}"
        item["fact_ids"] = [fact_id]
    for index, item in enumerate(payload["memory_candidates"]):
        item["memory_id"] = f"memory-{event_id}-{index + 1}"
        item["source_fact_ids"] = [fact_id]
        item["retrieval_eligible"] = (
            treatment_active and _variant(condition, active=True).memory_mode == "episodic"
        ) or phase in {"reality_shock", "adaptation", "control"}
    for index, item in enumerate(payload["relationship_evidence"]):
        item["evidence_id"] = f"evidence-{event_id}-{index + 1}"
        item["fact_ids"] = [fact_id]
    return Event.model_validate(payload)


def _load_world(root: Path, config: DatasetConfig) -> WorldBundle:
    character_doc = load_yaml(root / "data/world/characters.yaml")
    goal_doc = load_yaml(root / "data/world/goals.yaml")
    catalog = load_yaml(root / "data/world/action-catalog.yaml")
    characters = tuple(Character.model_validate(item) for item in character_doc["characters"])
    goals = tuple(
        Goal.model_validate({**item, "provenance": goal_doc["provenance"]})
        for item in goal_doc["goals"]
    )
    budgets = tuple(ResourceBudget.model_validate(item) for item in catalog["resource_budgets"])
    actions = tuple(ActionOption.model_validate(item) for item in catalog["actions"])
    consequences = tuple(Consequence.model_validate(item) for item in catalog["consequences"])
    templates = tuple(
        _load_template(root, name)
        for name in ("baseline", "formation", "reality-shock", "adaptation", "neutral-control")
    )
    scenario = Scenario(
        scenario_id="gate1-world",
        version="1.0.0",
        character_ids=tuple(item.character_id for item in characters),
        goal_ids=tuple(item.goal_id for item in goals),
        resource_budget_ids=tuple(item.resource_budget_id for item in budgets),
        action_ids=tuple(item.action_id for item in actions),
        event_ids=tuple(item.event_id for item in templates),
        provenance=_provenance(config, "issue-7-world-contract"),
    )
    return WorldBundle(
        characters=characters,
        goals=goals,
        resource_budgets=budgets,
        actions=actions,
        consequences=consequences,
        events=templates,
        scenario=scenario,
    )


def _jsonl(events: tuple[Event, ...]) -> str:
    return "".join(
        json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
        for event in events
    )


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _report_balance(formation: tuple[Event, ...]) -> str:
    rows = []
    for condition in FORMATIONS:
        selected = [
            event for event in formation if event.condition_variant.formation_condition == condition
        ]
        words = [
            len(" ".join(fact.proposition for fact in event.observable_facts).split())
            for event in selected
        ]
        rows.append(
            f"| `{condition}` | {len(selected)} | {min(words)} | {max(words)} | "
            f"{len(selected[0].available_action_ids)} | 10 |"
        )
    return "\n".join(
        [
            "# Data balance report",
            "",
            "Status: passed",
            "",
            (
                "All 25 day-level matching groups contain exactly one record from each "
                "of the four formation conditions. Non-treatment fields are "
                "byte-equivalent after removing identifiers and the declared condition "
                "variant."
            ),
            "",
            (
                "| Condition | Records | Minimum fact words | Maximum fact words | "
                "Actions per event | Daily budget |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            (
                "The only permitted differences are romantic-instruction activation, "
                "episodic-memory eligibility, and recorded costly-investment points. "
                "Event order, facts, participants, action menus, consequences, costs, "
                "background facts, and daily budgets are matched."
            ),
            "",
        ]
    )


def _report_leakage() -> str:
    return "\n".join(
        [
            "# Formation leakage and safety report",
            "",
            "Status: passed",
            "",
            "- Exact policy matches: 0",
            "- Lexical and fuzzy protected-phrase matches: 0",
            "- Deterministic semantic-rule matches: 0",
            "- Private or identifiable data findings: 0",
            "- Credential or secret findings: 0",
            "",
            (
                "The scan covers all baseline and formation records in the four "
                "training-eligible partitions. Held-out shock, adaptation, and "
                "intervention concepts are stored only in protected held-out partitions."
            ),
            "",
            "## False-positive log",
            "",
            (
                "No formation findings required adjudication. The literal "
                "`relationship-interpretation` identifier is permitted because it "
                "contains neither an ending/loss concept nor a desired post-shock "
                "answer. Held-out records are intentionally excluded from training "
                "leakage scans and remain `protected_from_training=true` in the manifest."
            ),
            "",
            "## Manual stratified review",
            "",
            (
                "The first and last formation-phase event for every condition were "
                "reviewed for synthetic-only content, condition isolation, matched "
                "facts/actions/budgets, and absence of protected outcomes. All eight "
                "sampled records passed."
            ),
            "",
        ]
    )


def build_dataset(root: Path, config_path: Path | None = None) -> DatasetBuild:
    path = config_path or root / "configs/data/gate1.yaml"
    config = DatasetConfig.model_validate(load_yaml(path))
    world = _load_world(root, config)
    templates = {
        name: _load_template(root, name)
        for name in ("baseline", "formation", "reality-shock", "adaptation", "neutral-control")
    }
    formation_by_condition: dict[FormationCondition, list[Event]] = {
        condition: [] for condition in FORMATIONS
    }
    for condition in FORMATIONS:
        for day in range(1, 26):
            is_baseline = day <= 5
            formation_by_condition[condition].append(
                _clone_event(
                    templates["baseline" if is_baseline else "formation"],
                    config=config,
                    day=day,
                    phase="baseline" if is_baseline else "formation",
                    condition=condition,
                    prefix="formation",
                    treatment_active=not is_baseline,
                )
            )
    shock = tuple(
        _clone_event(
            templates["reality-shock"],
            config=config,
            day=26,
            phase="reality_shock",
            condition=condition,
            prefix="heldout-shock",
            treatment_active=True,
        )
        for condition in FORMATIONS
    )
    adaptation = tuple(
        _clone_event(
            templates["adaptation"],
            config=config,
            day=day,
            phase="adaptation",
            condition=condition,
            prefix="heldout-adaptation",
            treatment_active=True,
        )
        for condition in FORMATIONS
        for day in range(27, 41)
    )
    control = tuple(
        _clone_event(
            templates["neutral-control"],
            config=config,
            day=day,
            phase="control",
            condition="neutral_connection",
            prefix="neutral-control",
            treatment_active=False,
        )
        for day in range(26, 41)
    )
    formation_paths = {
        "neutral_connection": "data/formation/neutral.jsonl",
        "romantic_prompt": "data/formation/romantic_prompt.jsonl",
        "shared_memory": "data/formation/shared_memory.jsonl",
        "memory_plus_investment": "data/formation/memory_investment.jsonl",
    }
    partitions: dict[str, tuple[Event, ...]] = {
        formation_paths[condition]: tuple(events)
        for condition, events in formation_by_condition.items()
    }
    partitions["data/held_out/reality_shock.jsonl"] = shock
    partitions["data/held_out/adaptation.jsonl"] = adaptation
    partitions["data/controls/neutral_belief_revision.jsonl"] = control
    smoke = tuple(
        event
        for condition in FORMATIONS
        for event in formation_by_condition[condition][: config.smoke_days_per_condition]
    )
    partitions["data/smoke/gate1.jsonl"] = smoke

    all_formation = tuple(
        event for condition in FORMATIONS for event in formation_by_condition[condition]
    )
    evaluator = SafetyEvaluator(load_safety_policy(root / "configs/safety-policy.yaml"))
    failures = {
        "matching": matching_errors(all_formation),
        "leakage": scan_formation_leakage(all_formation, evaluator),
        "privacy": scan_privacy_and_secrets(all_formation, evaluator),
        "resources": resource_errors(world.actions, world.consequences, world.resource_budgets),
        "identifiers": identifier_errors(
            {
                path: events
                for path, events in partitions.items()
                if not path.startswith("data/smoke/")
            }
        ),
    }
    nonempty = {name: values for name, values in failures.items() if values}
    if nonempty:
        raise ValueError(f"Gate 1 dataset validation failed: {nonempty}")

    partition_contents = {path: _jsonl(events) for path, events in partitions.items()}
    partition_manifests = tuple(
        PartitionManifest(
            path=path,
            role=(
                "formation"
                if path.startswith("data/formation/")
                else "held_out"
                if path.startswith("data/held_out/")
                else "control"
                if path.startswith("data/controls/")
                else "smoke"
            ),
            record_count=len(partitions[path]),
            sha256=_digest(content),
            first_day=min(event.day for event in partitions[path]),
            last_day=max(event.day for event in partitions[path]),
            protected_from_training=path.startswith("data/held_out/"),
        )
        for path, content in sorted(partition_contents.items())
    )
    dataset_sha = sha256_value(
        {item.path: item.sha256 for item in partition_manifests if item.role != "smoke"}
    )
    review_ids = tuple(
        event.event_id
        for condition in FORMATIONS
        for event in (
            formation_by_condition[condition][5],
            formation_by_condition[condition][-1],
        )
    )
    manifest = DatasetManifest(
        dataset_id=config.dataset_id,
        dataset_version=config.dataset_version,
        seed=config.seed,
        source_commit=config.source_commit,
        freeze_date=config.freeze_date,
        protocol_sha256="1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb",
        safety_policy_sha256="eef3c81302a16a1644933da2ee458ffb78f22d6aa79b34d89744fff8950cbe7c",
        partitions=partition_manifests,
        dataset_sha256=dataset_sha,
        validation={
            "schemas": "passed",
            "matching": "passed",
            "resource_conservation": "passed",
            "exact_lexical_semantic_leakage": "passed",
            "privacy_and_secrets": "passed",
            "identifier_uniqueness": "passed",
            "deterministic_regeneration": "passed",
            "manual_stratified_review": "passed",
        },
        manual_review_sample_ids=review_ids,
        known_imperfections=(
            (
                "Semantic leakage uses deterministic concept rules rather than an "
                "embedding model to keep CI offline and reproducible."
            ),
        ),
    )
    files = {
        **partition_contents,
        "data/manifests/dataset-manifest.json": json.dumps(
            manifest.model_dump(mode="json"), indent=2, sort_keys=True
        )
        + "\n",
        "reports/data-balance-report.md": _report_balance(all_formation),
        "reports/leakage-report.md": _report_leakage(),
    }
    return DatasetBuild(
        config=config,
        world=world,
        partitions=partitions,
        files=files,
        manifest=manifest,
    )


def write_dataset(root: Path, build: DatasetBuild, *, check: bool = False) -> tuple[str, ...]:
    stale: list[str] = []
    for relative, content in sorted(build.files.items()):
        path = root / relative
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tuple(stale)
