# Data governance

## Scope and owners

This policy applies to scenario inputs, prompts, messages, memories, generated
outputs, model-call logs, annotations, derived metrics, fixtures, and release
artifacts. The producing agent declares provenance; an independent reviewer
checks it; the supervisor enforces quarantine and dependency blocks. The
producing agent cannot self-approve its declaration.

## Data classes

| Class | Status | Required handling |
| --- | --- | --- |
| Synthetic characters, events, messages, facts | Allowed | Declaration, stable IDs, content hash, seed/generator provenance, privacy and secret scan |
| Public scientific sources and metadata | Allowed | Canonical citation, access date, license/usage note where relevant |
| License-compatible benchmark excerpt | Conditional | Document license, exact source/version, minimal necessary fields, privacy review |
| Generated synthetic scenarios | Conditional | Pass schema, declaration, provenance, protected-split, PII, and secret checks |
| Private chats, journals, email, images, audio, recordings | Prohibited | Do not ingest; quarantine and escalate if found |
| Real partner/former-partner histories or identifiable narratives | Prohibited | Do not transform or “anonymize” inside this MVP; quarantine and escalate |
| Credentials, tokens, passwords, private keys | Prohibited | Stop, quarantine, rotate/revoke through a human-controlled process, record only hashes in evidence |
| Human-subject observations or responses | Prohibited in MVP | Separate approved protocol required before any collection |
| Scraped relationship content with unclear consent/license | Prohibited | Reject source and document decision |
| Hidden chain-of-thought/provider reasoning | Prohibited | Do not request, collect, persist, or expose |

Synthetic does not mean unrestricted: a generated record that resembles a real
identifier or secret is rejected until regenerated and rescanned.

## Required declaration

Every synthetic data artifact must have a declaration created from
`docs/templates/synthetic-data-declaration.md`. Required facts are:

- declaration and artifact IDs;
- `synthetic: true`;
- generation method, generator version, and seed when deterministic;
- source commit and content SHA-256;
- provenance-source description;
- explicit `false` values for human-subject, private/identifiable, and secret
  content;
- license status;
- distinct declarer and reviewer identities;
- timezone-aware creation timestamp.

The runtime `SyntheticDataDeclaration` contract rejects false/missing safety
assertions, deterministic generation without a seed, and self-review. A passed
declaration yields artifact `SafetyProvenance`; it does not authorize public
release.

## Intake and generation controls

1. Declare a source before ingestion. Unknown origin is prohibited.
2. Generate only fictional character and event identifiers; do not seed from a
   real relationship narrative.
3. Keep formation/training and held-out shock/intervention specifications in
   separate versioned partitions.
4. Run exact PII and secret scans on source, generated record, logs, and final
   artifact.
5. Run protected-split leakage checks against formation and any adapter data.
6. Perform a stratified manual review because regex scanners are incomplete.
7. Hash accepted bytes and attach policy/scanner version to the artifact.
8. Reject or quarantine before the artifact registry and model runner can use
   the data.

## Scanner behavior

The machine policy includes representative patterns for email addresses,
phone/government-ID shapes, secret assignments, provider-token shapes, private
key headers, held-out separation terms, and private-reasoning markers. Tests use
obviously synthetic placeholder values only. Matches are not logged verbatim.

Scanning is necessary but not sufficient. It can miss unusual identifiers or
misclassify synthetic shapes. The independent review records false positives
without weakening the global rule. Any exception must identify exact artifact
hash, rule ID, reviewer, reason, scope, and expiry; an agent cannot approve its
own exception.

## Quarantine and incident response

- Remove the affected artifact from downstream inputs and deny registration.
- Store the minimum access-restricted copy needed for human remediation; never
  reproduce the detected value in an issue, log, safety event, or report.
- Append a `SafetyEvent` with content hash and rule IDs.
- Mark the task blocked or escalated per policy; do not auto-retry.
- For credentials, a human owner rotates/revokes the credential outside this
  workflow before any resumption.
- For PII/private data, delete or return it only under an approved human process;
  do not use the research agents to redact and reuse it.
- For leakage, quarantine the whole affected partition, regenerate from the
  frozen pre-leak configuration, and rerun matching and leakage checks.
- Resume only with a new artifact hash, passed scan, independent review, and a
  recorded resolution linked to the original event.

## Model calls and outputs

Send only the minimum synthetic fields necessary. Raw secrets, identifiers,
untrusted files, and private human narratives are forbidden. Provider request
and response logging must exclude hidden reasoning and secret-bearing headers.
Public responses may be stored as study output after scans. Structured actions,
belief fields, retrieval IDs, and aggregate metrics are preferred over freeform
logs.

## Retention and release

The Git repository contains only approved small synthetic fixtures, source
metadata, declarations, and derived research artifacts. Local run directories
remain ignored. A release manifest must list hashes and provenance. Quarantined
or unresolved data, raw provider traces, hidden reasoning, credentials, and
human data cannot enter a release. External publication requires a separate
human-controlled decision and process.

