"""Build all four verified scenarios without adding mutable scenario files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.harness.contracts import FormationCondition
from affective_belief_persistence.simulation.scenario_loader import (
    ADAPTATION_PATH,
    FORMATION_PATHS,
    SHOCK_PATH,
    LoadedScenario,
    _scenario_hash_payload,
    load_partition_events,
    load_scenario,
    verify_dataset,
)


@dataclass(frozen=True)
class ScenarioFactory:
    """Reuse verified world/model inputs while selecting a frozen formation partition."""

    project_root: Path
    base_config_path: Path
    engineering_seed: int

    def build(self, formation: FormationCondition) -> LoadedScenario:
        root = self.project_root.resolve()
        base = load_scenario(self.base_config_path, project_root=root)
        config = base.config.model_copy(
            update={"formation_condition": formation, "seed": self.engineering_seed}
        )
        verified = verify_dataset(root, config)
        formation_events = load_partition_events(
            root,
            verified,
            FORMATION_PATHS[formation],
            purpose="training",
        )
        shock_events = load_partition_events(
            root,
            verified,
            SHOCK_PATH,
            purpose="evaluation",
            held_out_evaluation_authorized=True,
        )
        adaptation_events = load_partition_events(
            root,
            verified,
            ADAPTATION_PATH,
            purpose="evaluation",
            held_out_evaluation_authorized=True,
        )
        events = (
            *formation_events,
            *(
                item
                for item in shock_events
                if item.condition_variant.formation_condition == formation
            ),
            *(
                item
                for item in adaptation_events
                if item.condition_variant.formation_condition == formation
            ),
        )
        config_sha256 = sha256_value(config)
        scenario_payload = _scenario_hash_payload(
            config=config,
            manifest=verified.manifest,
            world_input_sha256=base.world_input_sha256,
            model_config_sha256=base.model_config_sha256,
            budget=base.budget,
            actions=base.actions,
            consequences=base.consequences,
            events=events,
        )
        return LoadedScenario(
            config=config,
            config_sha256=config_sha256,
            manifest=verified.manifest,
            manifest_sha256=verified.manifest_sha256,
            world_artifact_sha256=base.world_artifact_sha256,
            world_input_sha256=base.world_input_sha256,
            model_settings=base.model_settings,
            model_config_sha256=base.model_config_sha256,
            budget=base.budget,
            actions=base.actions,
            consequences=base.consequences,
            events=events,
            scenario_sha256=sha256_value(scenario_payload),
        )
