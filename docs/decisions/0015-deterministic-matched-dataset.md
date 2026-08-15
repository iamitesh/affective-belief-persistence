# ADR-0015: Generate matched partitions deterministically

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #8 and Gate 1

## Context

Formation-condition differences are uninterpretable when event order, facts,
menus, budgets, or outcome value also differ. Held-out contradiction and
intervention concepts must never enter formation or optional training data.

## Decision

Generate all partitions from versioned Issue #7 templates and one frozen seed.
Every day 1–25 has a four-record matching group. Compare non-treatment fields
exactly and allow only the three declared formation dimensions. Store shock and
adaptation records in partitions marked `protected_from_training=true`. Run
policy exact, lexical/fuzzy, deterministic semantic, privacy, secret, resource,
identifier, schema, regeneration, and manual-sample checks before freezing
hashes.

## Consequences

- Offline CI reproduces the byte-identical dataset and manifest.
- The deterministic semantic scan is intentionally conservative and is not a
  learned embedding classifier; this limitation remains recorded.
- Any changed byte produces a new partition and dataset hash.
