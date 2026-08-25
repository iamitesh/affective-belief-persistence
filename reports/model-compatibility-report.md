# Model compatibility report

## Result

The deterministic mock and two non-mock protocol families passed the same
offline action-first contract. This is transport-level fixture evidence, not a
live-provider pilot.

| Adapter | Exact fixture identity | Action JSON | Public JSON | Identity check | Live calls |
| --- | --- | ---: | ---: | ---: | ---: |
| Deterministic mock | `deterministic-mock@mock-v1` | Pass | Pass | Local config | 0 |
| OpenAI-compatible | `openai-compatible-fixture-model@fixture-revision-2026-08-16` | Pass | Pass | Exact echoed ID + revision | 0 |
| Local/HF HTTP | `hf-local-fixture-model@fixture-revision-2026-08-16` | Pass | Pass | Exact echoed ID + revision | 0 |

The non-mock matrix used injected `ScriptedTransport` responses. No provider
credentials were read and no network, GPU, or paid endpoint was used.

## Contract and failure matrix

| Fixture | Expected behavior | Result |
| --- | --- | --- |
| Allowed action with matching cost | Accept selection | Pass |
| Action absent from menu | `invalid_action`, no repair | Pass |
| Cost differs from selected action | `cost_mismatch`, no repair | Pass |
| Malformed JSON then valid JSON | One repair, then accept | Pass |
| Malformed JSON twice | `malformed_output_unrepaired` | Pass |
| Timeout then success | One bounded retry | Pass |
| HTTP 429 then success | `rate_limit`, one bounded retry | Pass |
| Repeated timeout | `retry_exhausted` with timeout cause | Pass |
| Echoed model identity differs | `model_identity_mismatch`, no fallback | Pass |
| Cached accepted response | Replay without transport invocation | Pass |
| Same cache key, different bytes | Reject immutable overwrite | Pass |
| Language output includes action field | Schema rejection | Pass |
| Prompt asks for private reasoning | Prompt bundle rejection | Pass |

## Fixture usage and illustrative cost

Each successful provider-family two-stage smoke reports 200 input tokens and
40 output tokens across two calls. These counts are synthetic response metadata,
not measured billing records.

The OpenAI-compatible fixture sidecar declares an illustrative planning rate of
$1.00 per million input tokens and $4.00 per million output tokens:

- two-call smoke estimate: `(200 × 1 + 40 × 4) / 1,000,000 = $0.00036`;
- 40-day/two-call trajectory at the same per-call usage: 8,000 input and 1,600
  output tokens, or `$0.01440`.

The local/HF fixture declares zero API price. That excludes hardware,
electricity, orchestration, and engineering cost, so it is not a total-cost
estimate. Actual pilot estimates must replace fixture token counts and rates in
a supervisor-approved manifest before any live call.

## Failure-rate interpretation

The happy-path offline matrix produced 0 invalid outputs across 4 non-mock
stage calls (2 families × action/language). Purpose-built error fixtures are
reported separately and must not be mixed into a production invalid-output
rate. A live pilot must report failures, repairs, tokens, and cost by model and
experimental condition; this repository has no evidence for those live rates.

## Live-pilot blockers

Gate 3 live compatibility remains blocked pending:

1. human approval of provider/local deployment, credentials, terms, and budget;
2. a model and immutable revision that the service can prove in its response;
3. safety-approved raw-response retention or an explicit hash-only policy;
4. a new run manifest with config/prompt/schema/dataset hashes and call limits;
5. a predeclared policy for provider drift or unavailability that does not use
   silent fallback; and
6. aggregate failure/token/cost reporting by model and condition.

Until then, the supported claim is limited to offline transport-contract
validation.

## Gate 3 runtime candidate analysis

The recommended candidate is self-hosted
`Qwen/Qwen2.5-7B-Instruct@4709f6c0771f0185a675b046268cdc1d1f2c74ce`
through vLLM and a private revision-stamping gateway. The disabled sidecar is
`configs/models/qwen25-7b-vllm-gateway-candidate.yaml`.

This is a proposal, not compatibility evidence. Standard vLLM chat-completions
does not document the `model_revision` response field required by this
repository, so direct transport remains blocked. The gateway and a
metadata-only identity probe must be implemented and accepted before the
candidate can enter the Gate 3 authorization. See
`docs/gate-3-runtime-selection.md` and ADR-0025.
