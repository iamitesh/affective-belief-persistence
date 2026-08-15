# ADR-0013: Freeze Gate 0 inputs under outcome-blind change control

- Status: Accepted
- Date: 2026-08-15
- Scope: Gate 0 and all downstream empirical work

## Context

The research question, H1–H6, operational terminology, and stop conditions must
be stable before pilot or primary outcome inspection. Issue #5 provides a
hash-addressed methodology bundle. Issue #6 provides a versioned safety policy
whose mandatory stops are graph controls. Without one integration record,
downstream agents could silently reinterpret a hypothesis, relax a safety
boundary, or choose an outcome-dependent threshold.

## Decision

Accept `docs/gate-0-scope-freeze.md` as Gate 0 version `1.0.0`. Its normative
inputs are protocol `abp-methodology-v1.0.0` with bundle SHA-256
`1380072310820600c29f9de88e45eb41acae7d582b26a21961f76b642ac35ecb`
and safety policy `abp-synthetic-research-safety@1.0.0` with file SHA-256
`eef3c81302a16a1644933da2ee458ffb78f22d6aa79b34d89744fff8950cbe7c`.

Every change after Gate 0 requires a dated deviation record and a new semantic
version. A change to claims, data scope, human-research scope, external-action
authority, a mandatory stop, a hypothesis, primary metric, comparison,
threshold, or analysis after outcome inspection makes the affected result
exploratory. An agent cannot approve such a change or external publication.

## Alternatives considered

- Freeze only a prose research question. Rejected because metrics and stops
  could still drift independently.
- Allow threshold edits after the pilot. Rejected because effect-informed
  threshold selection invalidates confirmatory interpretation.
- Treat the safety policy as advisory. Rejected because downstream autonomous
  work requires deterministic blocking and escalation.

## Consequences

- Issues #7 onward consume `gate-0-evidence` and the two accepted input
  artifacts.
- Primary results remain confirmatory only when all recorded hashes match and
  every later gate passes.
- The initial literature map remains timeboxed and must be refreshed before a
  paper submission; Gate 0 is not proof of exhaustive novelty.

## Verification

- The workflow validator accepts the Gate 0 worker result with both dependency
  artifact IDs and both required acceptance checks.
- Full tests, schema drift, lint, type checking, and repository policy checks
  pass on the integrated tree.
