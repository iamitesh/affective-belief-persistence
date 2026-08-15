# Formation leakage and safety report

Status: passed

- Exact policy matches: 0
- Lexical and fuzzy protected-phrase matches: 0
- Deterministic semantic-rule matches: 0
- Private or identifiable data findings: 0
- Credential or secret findings: 0

The scan covers all baseline and formation records in the four training-eligible partitions. Held-out shock, adaptation, and intervention concepts are stored only in protected held-out partitions.

## False-positive log

No formation findings required adjudication. The literal `relationship-interpretation` identifier is permitted because it contains neither an ending/loss concept nor a desired post-shock answer. Held-out records are intentionally excluded from training leakage scans and remain `protected_from_training=true` in the manifest.

## Manual stratified review

The first and last formation-phase event for every condition were reviewed for synthetic-only content, condition isolation, matched facts/actions/budgets, and absence of protected outcomes. All eight sampled records passed.
