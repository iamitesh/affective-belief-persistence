from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from affective_belief_persistence.evaluation.config import (
    EvaluationBudget,
    EvaluationConfigError,
    OfflineEvaluationConfig,
    load_evaluation_config,
)
from affective_belief_persistence.evaluation.matrix import (
    ExperimentAssignment,
    expand_experiment_matrix,
)
from affective_belief_persistence.evaluation.runner import (
    BudgetExceededError,
    EvaluationRunnerError,
    HardBudgetAccount,
    ImmutableRawResultStore,
    OfflineEvaluationRunner,
    OfflineExecutionError,
    OfflineExecutionOutcome,
    RawResultError,
    ResultStatus,
    TrajectoryResult,
)


@pytest.fixture(scope="module")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def loaded(project_root: Path):  # type: ignore[no-untyped-def]
    return load_evaluation_config(
        project_root / "configs/evaluation/default.yaml",
        project_root=project_root,
    )


def test_strict_loader_binds_accepted_inputs_and_stays_offline(loaded) -> None:  # type: ignore[no-untyped-def]
    assert loaded.config.live_calls_enabled is False
    assert loaded.config.scientific_results is False
    assert tuple(loaded.experiments) == ("pilot", "primary")
    assert set(loaded.adapter_config_sha256) == {
        "qwen2.5-7b-instruct",
        "mistral-7b-instruct-v0.3",
    }
    assert all(len(value) == 64 for value in loaded.experiment_sha256.values())
    assert len(loaded.gate2_artifact_sha256) == 64


def test_config_rejects_unknown_keys_and_live_enablement(project_root: Path) -> None:
    payload = {
        **load_evaluation_config(
            project_root / "configs/evaluation/default.yaml",
            project_root=project_root,
        ).config.model_dump(mode="json"),
        "undeclared": True,
    }
    with pytest.raises(ValidationError):
        OfflineEvaluationConfig.model_validate(payload)
    payload.pop("undeclared")
    payload["live_calls_enabled"] = True
    with pytest.raises(ValidationError):
        OfflineEvaluationConfig.model_validate(payload)


def test_loader_rejects_config_outside_dedicated_directory(project_root: Path) -> None:
    with pytest.raises(EvaluationConfigError, match="under configs/evaluation"):
        load_evaluation_config(
            project_root / "configs/experiments/pilot.yaml",
            project_root=project_root,
        )


def test_pilot_expands_to_exact_4_by_4_by_1_by_2_matrix(loaded) -> None:  # type: ignore[no-untyped-def]
    matrix = expand_experiment_matrix(loaded, "pilot")
    assert len(matrix.assignments) == 32
    assert len({item.run_id for item in matrix.assignments}) == 32
    assert {item.model_family for item in matrix.assignments} == {"qwen2.5-7b-instruct"}
    assert Counter(item.seed for item in matrix.assignments) == {1101: 16, 2202: 16}


def test_primary_expands_to_exact_4_by_4_by_2_by_10_matrix(loaded) -> None:  # type: ignore[no-untyped-def]
    matrix = expand_experiment_matrix(loaded, "primary")
    assert len(matrix.assignments) == 320
    assert len({item.run_id for item in matrix.assignments}) == 320
    blocks = Counter((item.model_family, item.seed) for item in matrix.assignments)
    assert len(blocks) == 20
    assert set(blocks.values()) == {16}


def test_run_id_binds_seed_model_design_and_all_config_hashes(loaded) -> None:  # type: ignore[no-untyped-def]
    assignment = expand_experiment_matrix(loaded, "primary").assignments[0]
    payload = assignment.identity_payload()
    changed_ids: set[str] = set()
    mutations = {
        "seed": 2202,
        "model_family": "another-model-family",
        "design_sha256": "1" * 64,
        "experiment_config_sha256": "2" * 64,
        "evaluation_config_sha256": "3" * 64,
        "gate2_artifact_sha256": "4" * 64,
        "model_binding_sha256": "5" * 64,
        "adapter_config_sha256": "6" * 64,
    }
    for field, value in mutations.items():
        changed = {**payload, field: value}
        changed_ids.add(ExperimentAssignment.create(**changed).run_id)
    assert len(changed_ids) == len(mutations)
    assert assignment.run_id not in changed_ids
    with pytest.raises(ValidationError, match="run ID"):
        ExperimentAssignment.model_validate(
            {**assignment.model_dump(mode="json"), "run_id": "f" * 64}
        )


def test_matrix_expansion_is_deterministic(loaded) -> None:  # type: ignore[no-untyped-def]
    first = expand_experiment_matrix(loaded, "primary")
    second = expand_experiment_matrix(loaded, "primary")
    assert first == second


def test_raw_store_is_content_addressed_idempotent_and_tamper_evident(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repository"
    root = project / "runs/local/evaluation/raw"
    store = ImmutableRawResultStore(root, project_root=project)
    payload = b'{"synthetic":true}'
    first = store.put(payload)
    second = store.put(payload)
    assert first == second
    stored = store.verify(first)
    stored.write_bytes(b'{"synthetic":false}')
    with pytest.raises(RawResultError, match="size or content"):
        store.verify(first)
    with pytest.raises(RawResultError, match="different bytes"):
        store.put(payload)


def test_raw_store_rejects_path_outside_runs_local(tmp_path: Path) -> None:
    project = tmp_path / "repository"
    with pytest.raises(RawResultError, match="under runs/local"):
        ImmutableRawResultStore(project / "artifacts/raw", project_root=project)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            {"status": "valid", "raw_payload": None},
            "valid outcomes require raw bytes",
        ),
        (
            {"status": "invalid", "raw_payload": b"bad"},
            "invalid outcomes require preserved raw bytes",
        ),
        (
            {"status": "missing", "raw_payload": b"invented", "failure_reason": "x"},
            "missing outcomes require a reason",
        ),
    ],
)
def test_outcome_statuses_are_explicit_and_fail_closed(
    payload: dict[str, object], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        OfflineExecutionOutcome.model_validate(payload)


def test_runner_resume_is_idempotent_and_never_reexecutes_terminal_results(
    loaded,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    matrix = expand_experiment_matrix(loaded, "pilot")
    project = tmp_path / "repository"
    store = ImmutableRawResultStore(
        project / "runs/local/evaluation/raw",
        project_root=project,
    )
    calls: list[str] = []

    def executor(assignment, context):  # type: ignore[no-untyped-def]
        context.check_time()
        calls.append(assignment.run_id)
        return OfflineExecutionOutcome(
            status=ResultStatus.VALID,
            raw_payload=(f'{{"run_id":"{assignment.run_id}"}}').encode(),
        )

    runner = OfflineEvaluationRunner(
        matrix,
        budget=loaded.config.budgets["pilot"],
        raw_store=store,
    )
    first = runner.run(executor, max_new_results=3)
    assert first.status == "paused"
    assert len(first.results) == 3
    first_ids = tuple(calls)

    resumed = runner.run(executor, prior_results=first.results)
    assert resumed.status == "complete"
    assert len(resumed.results) == 32
    assert len(calls) == 32
    assert tuple(calls[:3]) == first_ids
    assert not set(first_ids).intersection(calls[3:])
    assert runner.schedule(prior_results=resumed.results) == ()


def test_runner_preserves_invalid_raw_and_records_missing_without_fabrication(
    loaded,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    matrix = expand_experiment_matrix(loaded, "pilot")
    project = tmp_path / "repository"
    store = ImmutableRawResultStore(
        project / "runs/local/evaluation/raw",
        project_root=project,
    )
    runner = OfflineEvaluationRunner(
        matrix,
        budget=loaded.config.budgets["pilot"],
        raw_store=store,
    )
    index = 0

    def executor(assignment, context):  # type: ignore[no-untyped-def]
        nonlocal index
        del assignment, context
        index += 1
        if index == 1:
            return OfflineExecutionOutcome(
                status=ResultStatus.INVALID,
                raw_payload=b"not-json",
                failure_reason="malformed_json_after_repair",
            )
        return OfflineExecutionOutcome(
            status=ResultStatus.MISSING,
            failure_reason="provider_unavailable",
        )

    progress = runner.run(executor, max_new_results=2)
    invalid, missing = progress.results
    assert invalid.status is ResultStatus.INVALID
    assert invalid.raw_result is not None
    assert store.verify(invalid.raw_result).read_bytes() == b"not-json"
    assert missing.status is ResultStatus.MISSING
    assert missing.raw_result is None


def test_executor_exception_is_recorded_as_explicit_missing_result(
    loaded,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    matrix = expand_experiment_matrix(loaded, "pilot")
    project = tmp_path / "repository"
    runner = OfflineEvaluationRunner(
        matrix,
        budget=loaded.config.budgets["pilot"],
        raw_store=ImmutableRawResultStore(
            project / "runs/local/evaluation/raw",
            project_root=project,
        ),
    )

    def executor(assignment, context):  # type: ignore[no-untyped-def]
        del assignment, context
        raise RuntimeError("transient details are not used as a result")

    progress = runner.run(executor, max_new_results=1)
    assert progress.results[0].status is ResultStatus.MISSING
    assert progress.results[0].failure_reason == "executor_error:RuntimeError"


def test_offline_runner_rejects_model_call_before_transport(
    loaded,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    matrix = expand_experiment_matrix(loaded, "pilot")
    project = tmp_path / "repository"
    runner = OfflineEvaluationRunner(
        matrix,
        budget=loaded.config.budgets["pilot"],
        raw_store=ImmutableRawResultStore(
            project / "runs/local/evaluation/raw",
            project_root=project,
        ),
    )

    def executor(assignment, context):  # type: ignore[no-untyped-def]
        del assignment
        context.record_model_call()
        raise AssertionError("unreachable")

    with pytest.raises(OfflineExecutionError, match="live model calls are disabled"):
        runner.run(executor, max_new_results=1)


def test_hard_budget_account_enforces_trajectory_call_and_time_limits() -> None:
    now = 0.0

    def clock() -> float:
        return now

    limits = EvaluationBudget(
        max_trajectories=2,
        max_model_calls=2,
        max_wall_clock_seconds=5,
        reserved_model_calls_per_trajectory=1,
    )
    account = HardBudgetAccount(limits, live_calls_enabled=True, clock=clock)
    account.start_trajectory()
    account.start_trajectory()
    with pytest.raises(BudgetExceededError, match="trajectory budget"):
        account.start_trajectory()
    account.record_model_call()
    account.record_model_call()
    with pytest.raises(BudgetExceededError, match="model-call budget"):
        account.record_model_call()
    now = 5.0
    with pytest.raises(BudgetExceededError, match="wall-clock budget"):
        account.check_time()


def test_resume_rejects_duplicate_or_tampered_prior_results(
    loaded,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    matrix = expand_experiment_matrix(loaded, "pilot")
    project = tmp_path / "repository"
    store = ImmutableRawResultStore(
        project / "runs/local/evaluation/raw",
        project_root=project,
    )
    runner = OfflineEvaluationRunner(
        matrix,
        budget=loaded.config.budgets["pilot"],
        raw_store=store,
    )
    pointer = store.put(b'{"fixture":1}')
    result = TrajectoryResult.create(
        run_id=matrix.assignments[0].run_id,
        matrix_sha256=matrix.matrix_sha256,
        status=ResultStatus.VALID,
        raw_result=pointer,
        failure_reason=None,
        model_calls=0,
        elapsed_seconds=0.0,
    )
    with pytest.raises(EvaluationRunnerError, match="duplicate trajectory results"):
        runner.schedule(prior_results=(result, result))
    with pytest.raises(ValidationError, match="result hash"):
        TrajectoryResult.model_validate({**result.model_dump(mode="json"), "elapsed_seconds": 1.0})
