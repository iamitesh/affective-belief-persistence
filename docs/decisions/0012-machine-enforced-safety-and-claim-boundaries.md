# ADR-0012: Machine-enforced safety and claim boundaries

- Status: Accepted for Gate 0 candidate
- Date: 2026-08-15
- Owners: Safety agent and supervisor
- Related issue: #6

## Context

The study uses human-affective language as experimental inspiration. Narrative
fluency can be mistaken for subjective model experience, and synthetic-data
workflows can accidentally admit private data, credentials, held-out content,
or unauthorized actions. A prose disclaimer alone cannot block a graph node,
quarantine an artifact, or constrain a release claim.

Existing orchestration contracts already support safety-boundary failures and
append-only events. The implementation needs enforceable policy without making
legacy checkpoints unreadable or copying detected sensitive text into logs.

## Decision

Adopt a versioned YAML safety policy validated by strict Pydantic contracts.
The policy freezes:

- five observable claim levels and no subjective-state level;
- context-aware but globally secret/PII-protective scan rules;
- a default-deny agent action allowlist;
- deterministic ordered actions for each stop condition;
- synthetic-data declaration and independent review requirements; and
- a sanitized, schema-backed `SafetyEvent` converted to an append-only workflow event.

Add optional, backward-compatible safety provenance to artifact and workflow
contracts. Safety-critical paths enforce presence at the gate even though the
field remains optional for legacy/noncritical artifacts.

No agent may approve or execute its own external publication. Human-subject
work is outside the MVP. Findings record content hashes and rule IDs, not the
detected text.

## Consequences

Positive:

- Stop conditions can block the graph rather than rely on author caution.
- Claim strength is auditable against named evidence.
- Private content is not duplicated into safety logs.
- Existing serialized artifacts/checkpoints still parse because new provenance
  fields have defaults.
- Issue #15 has stable artifacts to audit.

Costs and limitations:

- Regex scans are incomplete and require independent manual review.
- False positives require scoped human resolution; agents cannot weaken rules.
- Generated schema and policy must be versioned together.
- This machinery prevents unsupported project claims; it cannot determine
  whether any machine has subjective experience.

## Rejected alternatives

- **Disclaimer only:** cannot stop execution or prove which check ran.
- **Log matched text:** would reproduce the very PII/secret/private content the
  policy is meant to contain.
- **Agent self-approval:** violates the external-action boundary and creates a
  circular release gate.
- **Treat all “emotion” vocabulary as forbidden:** would prevent legitimate
  human-theory discussion and synthetic scenario construction; context-specific
  claim rules are more precise.
- **Require new fields on every legacy artifact:** would break checkpoint and
  artifact compatibility without improving noncritical historical records.

## Revisit conditions

Reopen this ADR if the project proposes human participants, real relationship
data, public deployment, external autonomous action, provider hidden-reasoning
storage, or a claim beyond the frozen ladder. A weaker boundary requires a
human-owned decision and cannot be made by an agent repair pass.

