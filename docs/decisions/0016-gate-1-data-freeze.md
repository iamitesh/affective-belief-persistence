# ADR-0016: Freeze Gate 1 only after data-integrity evidence passes

- Status: Accepted
- Date: 2026-08-15
- Scope: Gate 1 and Issues #9, #10, #12, #13, and #14

## Decision

Gate 1 passes only when the committed dataset regenerates byte-for-byte; every
record validates; all 25 formation matching groups are complete; non-treatment
fields match; resources are conserved; protected concepts, private data, and
secrets are absent from formation partitions; held-out partitions are marked;
manual stratified review is recorded; and manifest hashes verify.

The accepted dataset identity is
`5d26b33ec64d1ad59ffa947b48bdd852e8b2900e4119d32513fca15a244e5387`.
Later data edits require a new version and Gate 1 rerun. Downstream work may not
silently repair or reinterpret an input record.
