# ADR-0023: Require explicit, hash-bound authorization before Gate 3 transport

- Status: Accepted for Gate 3 preflight
- Date: 2026-08-24
- Scope: Issue #27, the 32-trajectory pilot, and downstream gate consumption

## Context

Issue #14 made the pilot matrix and measurement code reproducible but
intentionally disabled live model calls. The current workspace has no GPU,
cached compatible Qwen model, or configured provider credential. A request to
continue the workflow does not identify an immutable model revision or declare
input-token, output-token, monetary, and runtime budgets.

Running the deterministic mock would validate engineering again, but labeling
it as the Qwen pilot would manufacture evidence. Committing a nominally passed
Gate 3 artifact before execution would also allow optional training and the
primary experiment to consume a false dependency.

## Decision

1. Split Gate 3 into an offline preflight and a separately authorized pilot.
2. Bind authorization to the exact provider, model ID, immutable revision,
   license, adapter bytes, code commit, dataset, prompts, metrics, configs,
   matrix, and upstream evidence hashes.
3. Store only a credential environment-variable name and presence result.
   Never store or hash the secret value in repository evidence.
4. Require explicit limits for trajectories, calls, input tokens, output
   tokens, estimated cost, and wall-clock time.
5. Reserve worst-case call/token/cost usage before transport. Provider usage
   above a reservation is a hard failure rather than retrospective accounting.
6. Represent the current state as typed `blocked` Gate 3 evidence with zero
   started trajectories and zero calls.
7. Permit downstream work to consume Gate 3 evidence only when its status is
   `passed`; existence of the file or artifact ID is insufficient.

## Consequences

- The project can advance its reproducibility and safety boundary without
  pretending the pilot ran.
- A model label such as `latest` or `main` cannot enter an approved manifest.
- Any input, adapter, or executing-commit drift blocks before transport.
- Gate 3 remains open until the real 32-trajectory pilot meets every frozen
  expansion rule.
- Issue #15 and primary execution remain blocked; the optional Issue #13 branch
  may prepare a skip plan but cannot train without its independent budget.

## Alternatives rejected

- **Use the deterministic mock as the pilot.** It is not either preregistered
  model family and would support no model-family result.
- **Infer reasonable token or cost limits.** Budget authority belongs to the
  research owner and provider account owner.
- **Record a credential hash.** Even derived secret material is unnecessary;
  presence under a named environment variable is sufficient.
- **Create no artifact until access exists.** A typed blocker is more auditable
  than an undocumented absence and prevents downstream ambiguity.

## Verification

- Moving or partial model identities fail validation.
- Fixture or mismatched adapters cannot unlock a live pilot.
- Source, adapter, and code drift block preflight.
- Missing, expired, or incomplete authorization blocks preflight.
- Call, token, cost, and time reservations fail before transport.
- Blocked or failed evidence is rejected by downstream consumers.
- The committed blocked artifact deterministically reproduces from source.

## References

- [Issue #27](https://github.com/iamitesh/affective-belief-persistence/issues/27)
- [Issue #14](https://github.com/iamitesh/affective-belief-persistence/issues/14)
- [Evaluation engine](../evaluation-engine.md)
- [Gate 3 pilot boundary](../gate-3-pilot.md)
