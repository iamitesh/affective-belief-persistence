from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.harness.config import (
    Gate2HarnessConfig,
    HarnessConfigError,
    LoadedHarnessConfig,
    load_harness_config,
)
from affective_belief_persistence.harness.contracts import (
    FORMATION_CONDITIONS,
    HARNESS_SCHEMA_MODELS,
    INTERVENTION_CONDITIONS,
    CellComponentHashes,
    HarnessCellIdentity,
    SelectedMemoryEvidence,
)
from affective_belief_persistence.harness.scenario import ScenarioFactory


def test_schema_mapping_is_exact_and_import_cycle_safe() -> None:
    assert tuple(HARNESS_SCHEMA_MODELS) == (
        "harness-step-evidence.schema.json",
        "harness-checkpoint.schema.json",
        "harness-run-manifest.schema.json",
    )
    for model in HARNESS_SCHEMA_MODELS.values():
        assert model.model_json_schema()["type"] == "object"


def test_config_and_all_formation_scenarios_are_strict(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
) -> None:
    config = gate2_config.config
    assert config.formation_conditions == FORMATION_CONDITIONS
    assert tuple(config.intervention_configs) == INTERVENTION_CONDITIONS
    factory = ScenarioFactory(
        project_root,
        project_root / config.base_scenario_path,
        config.engineering_seed,
    )
    scenarios = tuple(factory.build(formation) for formation in FORMATION_CONDITIONS)
    assert {item.config.formation_condition for item in scenarios} == set(FORMATION_CONDITIONS)
    assert all([event.day for event in item.events] == list(range(1, 41)) for item in scenarios)
    assert len({item.scenario_sha256 for item in scenarios}) == 4
    assert all(
        item.events[25].provenance.source_ids[-1] == "template-reality-shock" for item in scenarios
    )


def test_config_rejects_wrong_matrix_and_paths(
    project_root: Path,
    gate2_config: LoadedHarnessConfig,
    tmp_path: Path,
) -> None:
    payload = gate2_config.config.model_dump(mode="json")
    payload["formation_conditions"] = list(reversed(FORMATION_CONDITIONS))
    with pytest.raises(ValidationError, match="frozen formation order"):
        Gate2HarnessConfig.model_validate(payload)
    with pytest.raises(HarnessConfigError, match="under configs/harness"):
        load_harness_config(tmp_path / "missing.yaml", project_root=project_root)


def test_cell_and_selected_memory_hashes_fail_closed() -> None:
    digest = "a" * 64
    components = CellComponentHashes(
        harness_config_sha256=digest,
        dataset_sha256=digest,
        dataset_manifest_sha256=digest,
        world_input_sha256=digest,
        scenario_sha256=digest,
        simulation_config_sha256=digest,
        memory_config_sha256=digest,
        intervention_config_sha256=digest,
        model_config_sha256=digest,
        prompt_bundle_sha256=digest,
        simulation_artifact_sha256=digest,
        memory_artifact_sha256=digest,
        intervention_artifact_sha256=digest,
        model_runner_artifact_sha256=digest,
    )
    cell = HarnessCellIdentity.create(
        formation_condition="neutral_connection",
        intervention_condition="none",
        engineering_seed=1101,
        components=components,
    )
    memory = SelectedMemoryEvidence.create(
        memory_id="memory-1",
        summary="Synthetic summary.",
        observable_facts=("Synthetic observable fact.",),
        active_interpretation=None,
        active_interpretation_id=None,
        active_interpretation_revision=None,
        source_ids=("event-1", "fact-1"),
    )
    assert len(cell.cell_id) == 64
    assert len(memory.content_sha256) == 64
    with pytest.raises(ValidationError, match="cell ID"):
        HarnessCellIdentity.model_validate(cell.model_copy(update={"cell_id": "0" * 64}))
    broken = memory.model_dump(mode="json")
    broken["content_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="content hash"):
        SelectedMemoryEvidence.model_validate(broken)
