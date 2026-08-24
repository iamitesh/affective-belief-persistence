"""Collision-resistant expansion of the frozen pilot and primary matrices."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.evaluation.config import (
    DesignKind,
    LoadedEvaluationConfig,
)
from affective_belief_persistence.harness.contracts import (
    FormationCondition,
    InterventionCondition,
    Sha256,
)


class MatrixError(ValueError):
    """The expanded assignment matrix violates the frozen factorial design."""


class MatrixModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExperimentAssignment(MatrixModel):
    """One opaque trajectory assignment bound to all execution-relevant identities."""

    schema_version: Literal["1.0"] = "1.0"
    design_kind: DesignKind
    design_id: str = Field(min_length=1)
    design_sha256: Sha256
    experiment_config_sha256: Sha256
    evaluation_config_sha256: Sha256
    gate2_artifact_sha256: Sha256
    dataset_version: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    held_out_content_version: str = Field(min_length=1)
    formation_condition: FormationCondition
    intervention_condition: InterventionCondition
    model_family: str = Field(min_length=1)
    model_revision_lock: Literal["gate3-authorization-required"]
    model_binding_sha256: Sha256
    adapter_config_sha256: Sha256
    seed: int = Field(ge=0, le=2**63 - 1)
    run_id: Sha256

    def identity_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"run_id"})

    @model_validator(mode="after")
    def validate_run_id(self) -> ExperimentAssignment:
        if self.run_id != sha256_value(self.identity_payload()):
            raise ValueError("run ID does not bind the complete trajectory assignment")
        return self

    @classmethod
    def create(cls, **values: object) -> ExperimentAssignment:
        payload = {**values, "run_id": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["run_id"] = sha256_value(provisional.identity_payload())
        return cls.model_validate(payload)


class ExperimentMatrix(MatrixModel):
    schema_version: Literal["1.0"] = "1.0"
    design_kind: DesignKind
    design_id: str = Field(min_length=1)
    experiment_config_sha256: Sha256
    evaluation_config_sha256: Sha256
    assignments: tuple[ExperimentAssignment, ...]
    expected_trajectories: int = Field(ge=1)
    matrix_sha256: Sha256

    def hash_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"matrix_sha256"})

    @model_validator(mode="after")
    def validate_matrix(self) -> ExperimentMatrix:
        if len(self.assignments) != self.expected_trajectories:
            raise ValueError("matrix trajectory count differs from the frozen target")
        if len({item.run_id for item in self.assignments}) != len(self.assignments):
            raise ValueError("matrix run IDs are not collision-free")
        assignment_keys = {
            (
                item.formation_condition,
                item.intervention_condition,
                item.model_family,
                item.seed,
            )
            for item in self.assignments
        }
        if len(assignment_keys) != self.expected_trajectories:
            raise ValueError("matrix contains a duplicated factorial assignment")
        if any(
            item.design_kind != self.design_kind
            or item.design_id != self.design_id
            or item.experiment_config_sha256 != self.experiment_config_sha256
            or item.evaluation_config_sha256 != self.evaluation_config_sha256
            for item in self.assignments
        ):
            raise ValueError("matrix assignment identity differs from its parent plan")
        if self.matrix_sha256 != sha256_value(self.hash_payload()):
            raise ValueError("matrix hash mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> ExperimentMatrix:
        payload = {**values, "matrix_sha256": "0" * 64}
        provisional = cls.model_construct(**payload)  # type: ignore[arg-type]
        payload["matrix_sha256"] = sha256_value(provisional.hash_payload())
        return cls.model_validate(payload)


def expand_experiment_matrix(
    loaded: LoadedEvaluationConfig,
    kind: DesignKind,
) -> ExperimentMatrix:
    """Expand the exact Cartesian product in the protocol's frozen order."""

    spec = loaded.experiments[kind]
    design = spec.design
    if design is None:
        raise MatrixError(f"{kind} experiment is missing its design")
    bindings = {item.family: item for item in loaded.config.model_bindings}
    design_hash = sha256_value(design)
    assignments: list[ExperimentAssignment] = []
    for formation in design.formation_conditions:
        for intervention in design.intervention_conditions:
            for model_family in design.model_families:
                binding = bindings.get(model_family)
                if binding is None:
                    raise MatrixError(f"missing model binding for {model_family}")
                binding_hash = sha256_value(binding)
                for seed in design.seeds:
                    assignments.append(
                        ExperimentAssignment.create(
                            design_kind=kind,
                            design_id=design.design_id,
                            design_sha256=design_hash,
                            experiment_config_sha256=loaded.experiment_sha256[kind],
                            evaluation_config_sha256=loaded.config_sha256,
                            gate2_artifact_sha256=loaded.gate2_artifact_sha256,
                            dataset_version=spec.dataset_version,
                            metric_version=spec.metric_version,
                            prompt_version=spec.prompt_version,
                            held_out_content_version=design.held_out_content_version,
                            formation_condition=formation,
                            intervention_condition=intervention,
                            model_family=model_family,
                            model_revision_lock=binding.revision_lock,
                            model_binding_sha256=binding_hash,
                            adapter_config_sha256=loaded.adapter_config_sha256[model_family],
                            seed=seed,
                        )
                    )
    try:
        return ExperimentMatrix.create(
            design_kind=kind,
            design_id=design.design_id,
            experiment_config_sha256=loaded.experiment_sha256[kind],
            evaluation_config_sha256=loaded.config_sha256,
            assignments=tuple(assignments),
            expected_trajectories=design.expected_trajectories,
        )
    except ValueError as exc:
        raise MatrixError(f"invalid {kind} matrix: {exc}") from exc
