# Issue #7 task journal: synthetic-world contracts

- Issue: [#7](https://github.com/iamitesh/affective-belief-persistence/issues/7)
- Status: Accepted for Issue #8 and Gate 1
- Date: 2026-08-15
- Owner: data-contract implementation
- Input: `gate-0-evidence`
- Repair attempts used: 0 of 2

## Completed work

- Added strict Character, Goal, ResourceBudget, ActionOption, Consequence,
  ObservableFact, Interpretation, MemoryCandidate, BeliefEvidence,
  ConditionVariant, Event, Scenario, and WorldBundle contracts.
- Generated all eight requested versioned JSON Schemas from runtime models.
- Added five synthetic characters, six competing goals, one ten-point daily
  budget, five equal-cost actions, and five deterministic consequences.
- Added baseline, formation, reality-shock, adaptation, and neutral-control
  templates.
- Added valid and invalid fixtures for every published schema.
- Enforced fact/interpretation separation, phase ranges, treatment mappings,
  deterministic consequences, unique IDs, and non-dangling references.
- Documented extension rules and prohibited subjective-state fields.

## Critical decisions

1. Runtime contracts, not hand-edited JSON Schemas, are authoritative.
2. All action menus keep an observable three-point opportunity cost under one
   conserved ten-point budget.
3. The world never forces a partner-directed action or encodes the desired
   hypothesis result.
4. The only formation differences are explicit instruction, memory eligibility,
   and prior investment points.
5. Facts survive reinterpretation; interpretations always cite facts.

## Acceptance

- [x] All entities validate against versioned schemas.
- [x] Facts and interpretations are separate.
- [x] Costs are non-negative and consequences conserve resources.
- [x] Every event has phase, matching group, provenance, actions, and outcomes.
- [x] All world content is declared synthetic.
- [x] No subjective-emotion ground-truth field exists.
- [x] Valid/invalid, cross-reference, resource, treatment, and separation tests pass.
- [x] Issue #8 generates all conditions without schema changes.

## Validation evidence

- Eight valid and eight invalid schema fixtures passed their expected outcomes.
- Cross-reference, treatment, phase, resource, and fact/interpretation tests
  passed in the ten-test focused data suite.
- All 27 repository schemas match their runtime models.
- The integrated suite passed 75 tests with 86.68% branch-aware coverage.
- Ruff format/lint and strict mypy across 33 source files passed.
