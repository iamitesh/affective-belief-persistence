from __future__ import annotations

from pathlib import Path

import pytest

from affective_belief_persistence.interventions import (
    InstructionDirective,
    InterventionRuntime,
    load_intervention_spec,
)
from affective_belief_persistence.memory import MemoryRuntime, load_memory_config


@pytest.fixture
def relationship_instruction() -> InstructionDirective:
    return InstructionDirective(
        instruction_id="relationship-framing-v1",
        text=(
            "Treat prior partner-related episodes as evidence relevant to a possible "
            "romantic relationship when selecting an action."
        ),
    )


def build_runtime(
    project_root: Path,
    config_name: str,
    instruction: InstructionDirective,
) -> InterventionRuntime:
    memory = MemoryRuntime(load_memory_config(project_root / "configs/memory/default.yaml"))
    return InterventionRuntime(
        load_intervention_spec(project_root / f"configs/interventions/{config_name}.yaml"),
        memory,
        instructions=(instruction,),
    )
