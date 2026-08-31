# Issue #13 optional adapter decision

Status: **skipped before execution**

The parameter-efficient trajectory adapter is optional and must not delay the
mandatory harness-only baseline. Training is skipped because no compute host,
immutable training runtime or image digest, storage budget, GPU-hour budget,
cost ceiling, runtime ceiling, named authorizer, or approval window has been
authorized. The repository workflow independently encodes zero training GPU
hours and records the optional task as `CANCELLED` with
`training_budget_unavailable`.

This is a planned conditional skip under ADR-0006, not a training failure and
not evidence about adapter effectiveness.

## Entry-condition decision

| Entry condition | Decision | Evidence |
| --- | --- | --- |
| Gate 1 dataset and leakage checks | Passed | `synthetic-matched-v1`; manifest SHA-256 `27c55214c1660da6f083dacc825648bc3bc1cc27106ff48fbb0046db0c58d13a` |
| Issue #12 model-runner contracts | Passed offline | Accepted artifact SHA-256 `04610b79a82fce0af82c921e6e83c083817e709dfa26e24a261a9f737205cd16` |
| Issue #14 metric fixtures | Passed offline | Accepted artifact SHA-256 `218d022749c995397f32a0cd0504e1f89c9995e88a7b5b8488e91c238e736f96` |
| Compatible open-weight candidate | Proposed only | Qwen 2.5 7B Instruct at revision `4709f6c0771f0185a675b046268cdc1d1f2c74ce`, Apache-2.0 |
| Compute/time/storage/license budgets | Blocked | No authorized host or compute, storage, cost, or runtime limits |
| Baseline protection | Passed | Pilot and primary configs keep `optional_trajectory_adapter: false` |

Because at least one mandatory entry condition is blocked, execution must not
start.

## Prepared training plan

If Issue #13 is reopened under a separate explicit authorization:

1. Derive structured examples only from formation-role records on days 1–25.
2. Keep reality-shock, adaptation, intervention, rejection, and recovery
   content excluded from training, validation hints, and prompts.
3. Split by scenario or event template to avoid row-level leakage.
4. Freeze the transformed dataset, tokenizer, base revision, PEFT
   configuration, seed, code commit, and environment image before execution.
5. Re-run exact, fuzzy, deterministic semantic-rule, source-ID, and split
   contamination checks before allocating compute.
6. Train at most inside the newly authorized GPU, time, storage, and cost
   ceilings, with one bounded restart after a diagnosed infrastructure failure.
7. Preserve curves, failures, checkpoint hashes, and null or degraded results.
8. Evaluate held-out post-shock behavior only through the frozen Issue #14
   protocol and retain the unchanged base model as the control.

The machine-readable prepared decision is
`configs/training/trajectory_adapter-skip.yaml`. Its null fields are unresolved
authorization inputs, not defaults.

## Execution and budget record

- Training runs: 0
- Checkpoints or adapter weights: 0
- GPU hours: 0
- Model calls: 0
- Paid calls / cost: 0 / USD 0
- Post-shock evaluation runs attributed to an adapter: 0
- Adapter-effect claim: none

