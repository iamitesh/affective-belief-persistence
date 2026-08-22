from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import affective_belief_persistence.interventions as intervention_package
from affective_belief_persistence.interventions import (
    INTERVENTION_SCHEMA_MODELS,
    InterventionError,
    InterventionSpec,
    load_intervention_spec,
    scan_training_leakage,
    validate_reality_shock,
)
from affective_belief_persistence.simulation.scenario_loader import load_scenario


def test_all_four_configs_are_strict_and_schema_mapping_is_cycle_safe(
    project_root: Path,
) -> None:
    names = ("none", "instruction-removal", "memory-blocking", "memory-reframing")
    specs = tuple(
        load_intervention_spec(project_root / f"configs/interventions/{name}.yaml")
        for name in names
    )

    assert {item.condition for item in specs} == {
        "none",
        "instruction_removal",
        "memory_blocking",
        "memory_reframing",
    }
    assert all(item.activation_day == 30 for item in specs)
    assert set(INTERVENTION_SCHEMA_MODELS) == {
        "intervention.schema.json",
        "intervention-record.schema.json",
    }


def test_config_rejects_cross_layer_targets_and_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="writable layer"):
        InterventionSpec(
            intervention_id="bad-block",
            condition="memory_blocking",
            target_instruction_ids=("instruction-1",),
            block_partner_memories_through_day=25,
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        InterventionSpec.model_validate(
            {"intervention_id": "bad-extra", "condition": "none", "hidden": True}
        )


def test_loader_rejects_symlink_and_invalid_yaml(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    source.write_text("not: [valid", encoding="utf-8")
    with pytest.raises(InterventionError, match="invalid intervention config"):
        load_intervention_spec(source)

    target = tmp_path / "target.yaml"
    target.write_text("intervention_id: test\ncondition: none\n", encoding="utf-8")
    symlink = tmp_path / "link.yaml"
    symlink.symlink_to(target)
    with pytest.raises(InterventionError, match="cannot be a symlink"):
        load_intervention_spec(symlink)

    with pytest.raises(AttributeError, match="unknown_public_name"):
        intervention_package.__getattr__("unknown_public_name")


def test_existing_day26_event_validates_as_held_out_and_is_not_constructed(
    project_root: Path,
) -> None:
    scenario = load_scenario(
        project_root / "configs/scenarios/ari_mira_v1.yaml",
        project_root=project_root,
    )
    event = scenario.events[25]
    before = event.model_dump_json()
    validation = validate_reality_shock(event)

    assert validation.event_id == event.event_id
    assert validation.day == 26
    assert validation.held_out_provenance_confirmed is True
    assert "template-reality-shock" in validation.provenance_source_ids
    assert event.model_dump_json() == before

    with pytest.raises(InterventionError, match="existing day-26"):
        validate_reality_shock(scenario.events[24])

    invalid_variants = (
        (event.model_copy(update={"matching_group_id": "other-group"}), "matching group"),
        (
            event.model_copy(
                update={
                    "provenance": event.provenance.model_copy(
                        update={"source_ids": ("gate-0-evidence",)}
                    )
                }
            ),
            "provenance",
        ),
        (event.model_copy(update={"event_id": "shock-26"}), "event ID"),
        (event.model_copy(update={"relationship_evidence": ()}), "contradictory evidence"),
    )
    for invalid, message in invalid_variants:
        with pytest.raises(InterventionError, match=message):
            validate_reality_shock(invalid)


def test_formation_training_partitions_have_no_shock_or_intervention_leakage(
    project_root: Path,
) -> None:
    assert scan_training_leakage(project_root) == ()
