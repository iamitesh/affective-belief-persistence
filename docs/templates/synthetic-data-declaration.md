# Synthetic-data declaration

Copy this template beside a data manifest and replace every placeholder. The
declarer and reviewer must be different identities. Do not paste source text,
PII, secrets, or matched scanner values into the declaration.

```yaml
schema_version: "1.0"
declaration_id: declaration-REPLACE
artifact_id: artifact-REPLACE
synthetic: true
generation_method: deterministic_generator  # hand_authored | deterministic_generator | model_generated
generator_version: generator-version-REPLACE
seed: 0  # required for deterministic_generator; null otherwise
source_commit: commit-sha-REPLACE
content_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
provenance_sources:
  - synthetic scenario specification REPLACE
contains_human_subject_data: false
contains_private_or_identifiable_data: false
contains_secrets: false
license_status: not_applicable  # not_applicable | license_documented
declared_by: producing-agent-REPLACE
reviewed_by: independent-reviewer-REPLACE
created_at: "2026-08-15T00:00:00Z"
```

Required attached evidence:

- exact artifact path, size, and content hash;
- generator/model configuration and seed;
- source IDs and license note where applicable;
- PII, secret, private-reasoning, and protected-split scan results;
- manual-review sample and reviewer identity;
- current safety policy ID/version/hash;
- any safety event and resolution IDs.

This declaration establishes provenance for internal research use. It does not
authorize external publication, human-subject research, or model deployment.

