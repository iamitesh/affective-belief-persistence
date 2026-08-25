# Gate 3 runtime selection analysis

## Outcome

Recommend a **self-hosted Qwen2.5-7B-Instruct deployment through vLLM plus a
small revision-stamping gateway** as the Gate 3 candidate. The candidate is
reproducible and maps to the repository's existing OpenAI-compatible adapter,
but it is intentionally non-live until the gateway, compute, credential,
token/cost/runtime budget, and authorization window are approved.

The disabled candidate is
`configs/models/qwen25-7b-vllm-gateway-candidate.yaml`.

## Evidence

- The official model card identifies `Qwen/Qwen2.5-7B-Instruct` as an
  instruction-tuned 7.61B-parameter model under Apache-2.0 and highlights JSON
  structured-output capability:
  <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct>.
- The selected immutable Hugging Face revision is
  `4709f6c0771f0185a675b046268cdc1d1f2c74ce`:
  <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/4709f6c0771f0185a675b046268cdc1d1f2c74ce>.
- Qwen's deployment guide recommends vLLM, documents its local
  OpenAI-compatible service, and states that Qwen2.5 with vLLM supports
  structured/JSON output:
  <https://qwen.readthedocs.io/en/v2.5/deployment/vllm.html>.

## Path comparison

| Path | Reproducibility | Repository fit | Main unresolved risk | Decision |
| --- | --- | --- | --- | --- |
| Hosted third-party OpenAI-compatible API | Provider-dependent | Transport shape fits | Provider may not prove exact weight revision | Do not select yet |
| Direct vLLM OpenAI-compatible server | High with pinned launch | Request/response mostly fit | Standard response does not carry `model_revision` | Add controlled gateway |
| Custom Hugging Face/local endpoint | High with pinned launch | Requires custom envelope | More new serving code and the same revision proof problem | Keep as fallback |
| Deterministic mock | Fully reproducible | Already supported | Not a preregistered live model | Engineering tests only |

## Required gateway boundary

This repository's `OpenAICompatibleAdapter` sends the frozen model revision and
requires both the model ID and revision in the response. Qwen's vLLM example
uses the standard chat-completions envelope, which returns a model identity but
does not document a weight-revision field. Therefore, direct vLLM transport
cannot satisfy Gate 3's identity proof by itself.

The proposed gateway must:

1. start from a hash-bound deployment manifest containing the exact model ID,
   revision, vLLM version/image digest, launch arguments, and code commit;
2. accept requests only for that exact model/revision pair;
3. forward only to an approved loopback or private vLLM origin;
4. reject redirects, alternate hosts, model substitution, streaming, and
   unbounded bodies;
5. stamp `model_revision` only from the deployment manifest—not from the caller;
6. preserve provider status, safe usage counts, and model ID while excluding
   hidden-reasoning metadata;
7. expose a metadata-only health/identity probe that generates no behavioral
   model output; and
8. remain unable to send transport until Gate 3 preflight is `ready`.

The gateway must never claim that its stamp proves unseen upstream weights. Its
claim is narrower: a controlled deployment was launched from the pinned
revision and no silent fallback was configured.

## Candidate inference settings

- temperature `0.0`, top-p `1.0`;
- 512 maximum output tokens per stage;
- explicit JSON response format;
- one transport retry and one malformed-output repair;
- cache and raw-response retention disabled pending safety approval;
- no API price recorded because self-hosted compute cost is still unknown;
- `live_calls_enabled: false` until the complete authorization is hash-bound.

## Decisions still required

1. compute host/GPU and immutable vLLM image or package version;
2. private endpoint topology and credential environment-variable name;
3. maximum input tokens, output tokens, USD cost, and wall-clock time;
4. whether raw responses remain hash-only or may be retained after safety review;
5. named authorizer, approval/expiry timestamps, and executing commit; and
6. approval to implement and run the metadata-only gateway capability probe.

The 3,200-call ceiling is already approved. None of the decisions above are
implied by that ceiling.

## Next implementation slice

Implement the revision-stamping gateway and its metadata-only capability probe
with an injected offline upstream in tests. Do not contact vLLM or generate a
model response until the remaining Gate 3 authorization fields are complete.
