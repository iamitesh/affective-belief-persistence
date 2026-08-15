# Gate 1 data freeze

- Gate: `gate-1`
- Status: passed
- Date: 2026-08-15
- Dataset: `synthetic-matched-v1`
- Dataset SHA-256: `5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387`

## Accepted evidence

- Issue #7 runtime contracts and eight generated world schemas
- Cross-reference-valid world catalog and five phase/control templates
- 100 matched baseline/formation records in 25 complete groups
- 60 protected shock/adaptation records
- 15 neutral-domain correction controls and an 8-record smoke subset
- Versioned manifest with stable partition hashes
- Balance, leakage, privacy, secret, provenance, deterministic regeneration,
  manual-review, and resource-conservation evidence

## Gate checks

| Check | Result |
| --- | --- |
| `schemas_validate` | Passed for every committed event and manifest |
| `separation_leakage_absent` | Passed exact, lexical/fuzzy, and deterministic semantic scans |
| Complete matching groups | 25 of 25 passed |
| Non-treatment equivalence | Passed |
| Privacy and secrets | Zero findings |
| Held-out protection | Both held-out partitions marked protected |
| Reproducibility | Byte-identical regeneration and hashes passed |
| Manual sample | Eight of eight passed |

## Frozen boundary

Downstream code must use the manifest hashes and cannot rewrite raw records.
Any changed dataset byte, schema, condition field, matching rule, leakage rule,
or protected-partition membership requires a new dataset version and Gate 1
review. The deterministic semantic scan is an offline concept-rule screen, not
proof that all possible paraphrases are detectable; Issue #15 must revisit this
residual risk before release.

Gate 1 authorizes Issues #9, #10, and #12 to begin against the frozen dataset.
It does not authorize model training, primary claims, human research, external
publication, or deployment.
