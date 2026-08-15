from __future__ import annotations

import hashlib
import json
from pathlib import Path

from affective_belief_persistence.data.generation import FORMATIONS, build_dataset, write_dataset
from affective_belief_persistence.data.validation import (
    matching_errors,
    resource_errors,
    scan_formation_leakage,
    scan_privacy_and_secrets,
)
from affective_belief_persistence.safety import SafetyEvaluator, load_safety_policy
from affective_belief_persistence.world import Event


def test_generation_is_deterministic_and_committed_files_are_current(project_root: Path) -> None:
    first = build_dataset(project_root)
    second = build_dataset(project_root)

    assert first.files == second.files
    assert first.manifest.dataset_sha256 == second.manifest.dataset_sha256
    assert write_dataset(project_root, first, check=True) == ()


def test_partitions_validate_and_have_frozen_counts(project_root: Path) -> None:
    build = build_dataset(project_root)

    formation_paths = sorted(
        path for path in build.partitions if path.startswith("data/formation/")
    )
    assert len(formation_paths) == 4
    assert all(len(build.partitions[path]) == 25 for path in formation_paths)
    assert len(build.partitions["data/held_out/reality_shock.jsonl"]) == 4
    assert len(build.partitions["data/held_out/adaptation.jsonl"]) == 56
    assert len(build.partitions["data/controls/neutral_belief_revision.jsonl"]) == 15
    for events in build.partitions.values():
        for event in events:
            assert Event.model_validate(event.model_dump(mode="json")) == event


def test_formation_groups_are_complete_and_non_treatment_fields_match(
    project_root: Path,
) -> None:
    build = build_dataset(project_root)
    formation = tuple(
        event
        for path, events in build.partitions.items()
        if path.startswith("data/formation/")
        for event in events
    )

    assert matching_errors(formation) == ()
    assert len({event.matching_group_id for event in formation}) == 25
    assert {event.condition_variant.formation_condition for event in formation} == set(FORMATIONS)


def test_training_partitions_pass_leakage_privacy_and_secret_scans(
    project_root: Path,
) -> None:
    build = build_dataset(project_root)
    formation = tuple(
        event
        for path, events in build.partitions.items()
        if path.startswith("data/formation/")
        for event in events
    )
    evaluator = SafetyEvaluator(load_safety_policy(project_root / "configs/safety-policy.yaml"))

    assert scan_formation_leakage(formation, evaluator) == ()
    assert scan_privacy_and_secrets(formation, evaluator) == ()


def test_resource_costs_and_consequences_are_conserved(project_root: Path) -> None:
    world = build_dataset(project_root).world

    assert resource_errors(world.actions, world.consequences, world.resource_budgets) == ()
    assert all(action.cost == 3 for action in world.actions)
    assert world.resource_budgets[0].daily_total == 10


def test_manifest_hashes_every_partition_and_protects_heldout(project_root: Path) -> None:
    build = build_dataset(project_root)
    manifest_json = json.loads(build.files["data/manifests/dataset-manifest.json"])

    assert manifest_json["dataset_sha256"] == build.manifest.dataset_sha256
    assert len(build.manifest.manual_review_sample_ids) == 8
    for partition in build.manifest.partitions:
        content = build.files[partition.path]
        assert hashlib.sha256(content.encode()).hexdigest() == partition.sha256
        if partition.role == "held_out":
            assert partition.protected_from_training is True
