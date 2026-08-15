# ADR-0014: Make runtime contracts authoritative for the synthetic world

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #7 and downstream simulation, memory, and data work

## Context

The experiment needs synthetic characters, goals, actions, resources, facts,
interpretations, memories, consequences, condition variants, and timelines.
Loose JSON would allow dangling references, hidden treatment fields, or an
unobserved subjective-state label to enter downstream work.

## Decision

Use frozen Pydantic models in `world.py` as the source of truth and generate all
eight required JSON Schemas from them. Reject unknown fields. Validate reference
integrity through `WorldBundle`. Keep authoritative facts and evidence-linked
interpretations as different types. Restrict treatment variation to the exact
fields enforced by `ConditionVariant`.

## Consequences

- Issue #8 and the simulator consume the same contracts.
- A new treatment field requires a Gate 0 version/deviation record.
- There is no field for model feeling, consciousness, or human-like emotion
  ground truth.
- Schema drift fails CI.
