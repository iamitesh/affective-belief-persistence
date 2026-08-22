# Reproducible model runner

## Scope and current claim

Issue #12 provides a provider-neutral, action-first inference boundary for the
accepted Issue #9 simulator. It validates two non-mock HTTP protocol families
through injected deterministic transports: an OpenAI-compatible
chat-completions shape and a local/Hugging Face text-generation shape. The
repository does not create a network client, read credentials, or make a paid
call.

The current evidence supports **offline transport-contract compatibility**.
It does not establish live compatibility with a hosted provider, a specific
deployed checkpoint, or provider-side reproducibility. A live pilot remains
blocked until a human owner approves credentials, terms, budget, pinned model
identity, response-retention policy, and a new run manifest.

## Action-first API

All real-family adapters implement the Issue #9 two-stage interface:

```python
selection = adapter.select_action(request, seed=action_seed)

# The simulator validates, commits, and debits the selected action here.

public_response = adapter.generate_public_language(
    request,
    selection,
    action_commitment_sha256=commitment_id,
    seed=language_seed,
)
```

`select_action` returns `ActionSelection`, which has no public-response field.
`generate_public_language` accepts the immutable action commitment and returns
only public text. The language JSON contract rejects action fields, so prose
cannot choose or retroactively replace an action.

The richer `select_action_input(ModelInput, seed=...)` method accepts goals,
finite resources, retrieved-memory records, beliefs with confidence and
evidence IDs, intervention metadata, phase, prompt version, and output-schema
version. `input_from_request` is the compatibility bridge for the narrower
frozen Issue #9 `DecisionRequest`; it does not invent goals or intervention
metadata that the upstream contract does not expose.

## Modules

| Module | Responsibility |
| --- | --- |
| `models/contracts.py` | Strict, immutable input/output/config/provenance contracts and cycle-safe schema map |
| `models/base.py` | Two-stage adapter, config loader, retries, repair, provenance, and Issue #9 bridge |
| `models/openai_compatible.py` | Chat-completions request/response transport shape |
| `models/hf_local.py` | Local/HF text-generation request/response transport shape |
| `models/mock.py` | Deterministic offline mock with legacy and two-stage APIs |
| `models/prompt_builder.py` | Versioned prompt loading and deterministic rendering |
| `models/output_parser.py` | Strict JSON, schema, action, cost, memory, and public-language checks |
| `models/cache.py` | Immutable content-addressed safe-response cache |
| `models/errors.py` | Stable failure categories and retryability |
| `models/transport.py` | Injected transport protocol and scripted offline transport |

`MODEL_RUNNER_SCHEMA_MODELS` exposes cycle-safe runtime sources for:

- `model-input.schema.json`
- `model-action-output.schema.json`
- `public-language-output.schema.json`
- `model-invocation-record.schema.json`

The pre-existing `model-decision.schema.json` remains sourced by the frozen
root `ModelDecision`. Issue #12 does not overwrite it.

## Configuration and identity

Runner configs are strict sidecars under `configs/models/` and do not mutate
the frozen root `ModelConfig` or `configs/models/mock.yaml`. Every invocation
records:

- provider family, adapter version, exact requested model ID and revision;
- config, prompt, model-input, call, cache-key, and response SHA-256 digests;
- run ID, stage, attempt, repair flag, seed, schema version, cache status; and
- ordinary input/output token counts when present.

Both real-family response envelopes must echo the exact model ID and revision.
Missing or different identity fails with `model_identity_mismatch`; the runner
does not switch adapters, providers, models, or revisions. Any change requires
a different strict config and therefore a different config hash and run ID.

The checked-in real-family configs name fixture identities and keep
`live_calls_enabled: false`. They are compatibility fixtures, not deployable
provider declarations.

## Validation, repair, and failure behavior

Provider text must be a single strict JSON object. Markdown fences, duplicate
keys, non-finite numbers, undeclared fields, and schema drift are invalid.
The action stage additionally proves:

- `chosen_action_id` exists in the supplied menu;
- `resources_spent` equals that action's frozen cost;
- cited memory IDs were retrieved; and
- belief evidence IDs exist in the event or supplied memory references.

Malformed JSON or schema-invalid output receives exactly one deterministic
repair prompt for that stage. A second failure raises
`malformed_output_unrepaired`; it never invents an action. A valid-looking but
unknown action or cost mismatch is a semantic contract failure and is not sent
through repair.

Transport timeouts, HTTP 429 responses, and 5xx responses are normalized and
retried only up to `max_transport_retries` (maximum two). Other 4xx responses,
provider-envelope errors, safety failures, and identity mismatches are not
retried. `RetryExhaustedError.cause_category` preserves the final normalized
cause.

## Cache and deterministic replay

`SafeResponseCache` addresses successful response artifacts by a digest over
the provider, exact identity, adapter config, prompt, input, stage, seed, and
credential-free request body. Headers are excluded and never persisted.

Raw provider envelopes enter the cache only when an injected retention policy
explicitly approves them. The safe default stores hashes only and therefore
does not create a replay cache. Existing entries are hash-validated,
symlink-rejected, and immutable: the same key cannot be overwritten with
different bytes.

Provider-family deterministic replay must use those previously validated,
immutable cached response artifacts. It must never call a live provider to
“reproduce” an earlier response. Cache misses in an offline replay are failures,
not authorization to use the network.

## Prompt privacy

Prompts are versioned in `prompts/decision/`. They request JSON, one allowed
action, a release-safe concise evidence summary, and public language after the
commitment. They do not request step-by-step or hidden reasoning. Provider
envelopes containing common hidden-reasoning or reasoning-token metadata are
rejected. Invocation records never contain provider credentials or reasoning
tokens.

## Offline verification

```bash
pytest tests/models -q
ruff check src/affective_belief_persistence/models tests/models
mypy src/affective_belief_persistence/models
```

See `reports/model-compatibility-report.md` for the smoke matrix, failure
fixtures, and illustrative cost calculation.

## Known limitations and escalation conditions

- No live provider, authentication, streaming, or paid-call client is included.
- Fixture token usage and pricing are illustrative, not vendor measurements or
  current price quotes.
- Exact revision echo is stricter than some hosted APIs support. A provider
  unable to prove its deployed revision is ineligible unless the methodology
  and claim boundary are explicitly revised.
- Issue #9 does not expose full goal, memory content, confidence, or
  intervention context. Issues #10 and #11 should construct `ModelInput`
  directly or add an approved upstream integration without changing hashed v1
  records.
- Raw response retention needs the full safety evaluator in an authorized live
  run; the synthetic fixture policy is not a production safety scanner.
- Escalate provider drift, inability to pin identity, retention restrictions,
  excessive invalid-output rates, unavailable models, or projected budget
  overruns. Never substitute an undeclared model.
