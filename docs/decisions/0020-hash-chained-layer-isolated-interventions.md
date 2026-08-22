# ADR-0020: Use transaction-bound, layer-isolated intervention sidecars

- Status: Accepted for Issue #11 implementation
- Date: 2026-08-22
- Scope: Issue #11, Gate 2, and downstream evaluation

## Context

Issue #11 needs to change instructions, retrieval, or interpretation on day 30
without changing authoritative facts or the accepted Issue #9 hashed v1
contracts. The memory intervention must influence the same day's retrieval, but
a failed action or public-language stage must not leave an applied treatment.
The Issue #12 `ModelInput` can carry intervention context, while the legacy
Issue #9 `DecisionRequest` cannot represent prompt instructions.

A naïve treatment label in the prompt would add an unintended second
manipulation. Globally blocking the `partner_related` tag would also remove the
held-out day-26 contradictory memory and confound the intended pre-shock memory
intervention.

## Decision

Keep intervention records in a separate hash-chained sidecar. Stage day-30
mutation before retrieval, but append its record only with the successful
simulation-step commit. Preserve the pre-action memory checkpoint and
instruction IDs so failure, retry, or a durability boundary can roll back an
uncommitted mutation.

Freeze blocking and reframing targets to stored, partner-related episodes with
`simulation_day <= 25`. Blocking writes only exact IDs to the retrieval filter.
Reframing appends an interpretation revision that cites the original fact IDs;
it never replaces raw episodes, prior revisions, or source-event IDs.

Represent instructions as explicit `InstructionDirective` values. The rich
model-input overlay receives only matched active instruction IDs, text, and a
state hash. Do not disclose the condition label, treatment-specific ID,
application-record hash, or blocked count to the model. Blocking and reframing
act through memory state only; instruction removal acts through absence of the
previously active directive.

Bind the intervention checkpoint to the exact simulation state and complete
memory checkpoint. Validate the existing day-26 event and its protected
provenance rather than inserting another shock event.

## Consequences

- A failed day-30 model stage cannot be checkpointed as a completed treatment.
- No-treatment is a provable zero-mutation condition.
- Day-26 contradiction and post-shock memories remain retrievable in the
  blocking arm.
- Reframe auditing can compare raw facts, prior interpretation, new revision,
  and source IDs.
- Provider prompts do not reveal the experimental assignment.
- Composite runners must explicitly consume `prepare_pre_action`; the legacy
  Issue #9 bridge remains a mechanical offline test path.
- Checkpoints are larger because they include simulation identity, memory, and
  intervention state together.

## Alternatives considered

- **Populate `SimulationStepRecord.applied_intervention_ids`.** Rejected because
  the accepted v1 validator prohibits non-empty values and changing it would
  invalidate Issue #9 hashes.
- **Apply permanently from the pre-action hook.** Rejected because a later model
  failure would leave a treatment without a committed simulation step.
- **Block the `partner_related` tag.** Rejected because it would also hide the
  reliable day-26 contradiction and later partner events.
- **Tell the model which treatment it received.** Rejected because assignment
  disclosure is a second prompt-layer manipulation.
- **Replace memory interpretations in place.** Rejected because it destroys the
  prior evidence state.

## Verification

- [x] Day-26 validation accepts the selected held-out event and rejects a
  formation event.
- [x] All four treatments activate at day 30 exactly once.
- [x] A failed day-30 language stage rolls back the staged intervention.
- [x] No-treatment has identical before/after snapshots.
- [x] Instruction removal changes only active directive IDs/text.
- [x] Blocking preserves storage and excludes only frozen pre-shock IDs.
- [x] Reframing preserves facts/source IDs and appends revision 2.
- [x] Assignment labels and intervention hashes are absent from model input.
- [x] Checkpoint restore rejects a different simulation state.
- [x] Formation/training leakage scan returns zero findings.

## References

- [Issue #11](https://github.com/iamitesh/affective-belief-persistence/issues/11)
- [Intervention design](../intervention-design.md)
- [Issue #11 task journal](../implementation/issue-11-task-journal.md)
- [ADR-0017](0017-deterministic-action-first-simulation.md)
- [ADR-0018](0018-event-sourced-memory-sidecar.md)
- [ADR-0019](0019-provider-neutral-structured-model-runner.md)
