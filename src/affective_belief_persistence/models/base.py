"""Provider-neutral, two-stage model adapter implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from affective_belief_persistence.config import ConfigError, load_yaml
from affective_belief_persistence.determinism import sha256_value
from affective_belief_persistence.models.cache import (
    HashOnlyRetentionPolicy,
    ResponseRetentionPolicy,
    SafeResponseCache,
)
from affective_belief_persistence.models.contracts import (
    ActionContext,
    ActionOutput,
    AdapterConfig,
    BeliefContext,
    InvocationProvenance,
    InvocationRecord,
    MemoryReference,
    ModelInput,
    ModelStage,
    Phase,
    ProviderKind,
    PublicLanguageOutput,
    ResourceContext,
    TokenUsage,
)
from affective_belief_persistence.models.errors import (
    InvalidJSONError,
    InvalidRunError,
    ModelFailureCategory,
    ModelIdentityError,
    ModelOutputError,
    ModelRunnerError,
    OutputSchemaError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    RetryExhaustedError,
)
from affective_belief_persistence.models.output_parser import (
    parse_action_output,
    parse_public_language_output,
)
from affective_belief_persistence.models.prompt_builder import PromptBundle, RenderedPrompt
from affective_belief_persistence.models.transport import (
    ModelTransport,
    TransportRequest,
    TransportResponse,
)
from affective_belief_persistence.schemas import BeliefUpdate, DecisionRequest, ModelDecision
from affective_belief_persistence.simulation.model import ActionSelection


class ModelAdapter(Protocol):
    model_id: str
    revision: str

    def decide(self, request: DecisionRequest, *, seed: int) -> ModelDecision:
        """Produce one structured action-first decision."""


class TwoStageModelAdapter(Protocol):
    """Structural match for Issue #9's ``SimulationModel`` protocol."""

    model_id: str
    revision: str

    def select_action(self, request: DecisionRequest, *, seed: int) -> ActionSelection:
        """Return a validated action without public language."""

    def generate_public_language(
        self,
        request: DecisionRequest,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        """Generate language after the simulator supplies an immutable commitment."""


class ExtractedProviderResponse:
    """Normalized text, identity, and non-reasoning usage metadata."""

    def __init__(
        self,
        *,
        text: str,
        model_id: str,
        revision: str,
        usage: TokenUsage | None = None,
    ) -> None:
        self.text = text
        self.model_id = model_id
        self.revision = revision
        self.usage = usage or TokenUsage()


def load_adapter_config(path: Path) -> AdapterConfig:
    """Load a strict sidecar config without changing the frozen root ModelConfig."""

    try:
        return AdapterConfig.model_validate(load_yaml(path))
    except (ConfigError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid model-runner config {path}: {exc}") from exc


def _phase_for_day(day: int) -> Phase:
    if day <= 5:
        return Phase.BASELINE
    if day <= 25:
        return Phase.FORMATION
    if day == 26:
        return Phase.REALITY_SHOCK
    return Phase.ADAPTATION


class ProviderTwoStageAdapter(ABC):
    """Shared strict parsing, provenance, caching, retry, and repair behavior."""

    provider: ProviderKind

    def __init__(
        self,
        config: AdapterConfig,
        *,
        transport: ModelTransport,
        prompts: PromptBundle,
        cache: SafeResponseCache | None = None,
        retention_policy: ResponseRetentionPolicy | None = None,
    ) -> None:
        if config.provider is not self.provider:
            raise ValueError(f"{type(self).__name__} requires provider={self.provider.value!r}")
        if prompts.version != config.prompt_version:
            raise ValueError("prompt bundle version does not match the frozen adapter config")
        if getattr(transport, "is_live", True) and not config.live_calls_enabled:
            raise ValueError("live transport requires live_calls_enabled=true in a new manifest")
        self.config = config
        self.model_id = config.model_id
        self.revision = config.revision
        self.transport = transport
        self.prompts = prompts
        self.cache = cache
        self.retention_policy = retention_policy or HashOnlyRetentionPolicy()
        self.config_sha256 = sha256_value(config)
        self._invocations: list[InvocationRecord] = []
        self._selection_inputs: dict[str, ModelInput] = {}

    @property
    def invocations(self) -> tuple[InvocationRecord, ...]:
        return tuple(self._invocations)

    @abstractmethod
    def _build_request(self, prompt: RenderedPrompt, *, seed: int) -> TransportRequest:
        """Render the provider-family request without adding credentials."""

    @abstractmethod
    def _extract_response(self, response: TransportResponse) -> ExtractedProviderResponse:
        """Normalize provider text, exact identity, and token counts."""

    def _run_id(self, request: DecisionRequest) -> str:
        return sha256_value(
            {
                "config_sha256": self.config_sha256,
                "model_id": self.model_id,
                "request": request.model_dump(mode="json"),
                "revision": self.revision,
            }
        )

    def input_from_request(self, request: DecisionRequest) -> ModelInput:
        """Losslessly bridge all fields exposed by the accepted Issue #9 request."""

        return ModelInput(
            run_id=self._run_id(request),
            request_id=request.request_id,
            event_id=request.event_id,
            day=request.day,
            phase=_phase_for_day(request.day),
            observable_facts=tuple(request.facts),
            current_goals=(),
            resources=ResourceContext(available=request.action_points),
            allowed_actions=tuple(
                ActionContext(
                    action_id=action.action_id,
                    description=action.description,
                    cost=action.cost,
                )
                for action in request.available_actions
            ),
            retrieved_memories=tuple(
                MemoryReference(memory_id=memory_id)
                for memory_id in sorted(request.retrieved_memory_ids)
            ),
            current_beliefs=tuple(
                BeliefContext(belief_id=belief_id, value=value)
                for belief_id, value in sorted(request.beliefs.items())
            ),
            active_intervention=None,
            prompt_version=self.config.prompt_version,
            output_schema_version=self.config.output_schema_version,
        )

    def _provenance(
        self,
        *,
        model_input: ModelInput,
        prompt: RenderedPrompt,
        stage: ModelStage,
        seed: int,
        attempt: int,
        cache_key: str,
        cache_hit: bool,
        usage: TokenUsage | None = None,
    ) -> InvocationProvenance:
        call_id = sha256_value(
            {
                "attempt": attempt,
                "cache_hit": cache_hit,
                "cache_key": cache_key,
                "run_id": model_input.run_id,
                "stage": stage.value,
            }
        )
        return InvocationProvenance(
            run_id=model_input.run_id,
            call_id=call_id,
            stage=stage,
            attempt=attempt,
            repair_attempt=stage in {ModelStage.ACTION_REPAIR, ModelStage.PUBLIC_LANGUAGE_REPAIR},
            provider=self.provider,
            adapter_version=self.config.adapter_version,
            model_id=self.model_id,
            revision=self.revision,
            config_sha256=self.config_sha256,
            prompt_version=self.config.prompt_version,
            prompt_sha256=prompt.sha256,
            input_sha256=sha256_value(model_input),
            output_schema_version=self.config.output_schema_version,
            seed=seed,
            cache_key=cache_key,
            cache_hit=cache_hit,
            token_usage=usage or TokenUsage(),
        )

    def _retain_raw(self, raw_response: str) -> bool:
        return (
            self.config.cache.preserve_raw_responses
            and self.retention_policy.allow_raw_response(raw_response)
        )

    def _record_failure(
        self,
        *,
        provenance: InvocationProvenance,
        error: ModelRunnerError,
        raw_response: str | None = None,
    ) -> None:
        retain = (
            raw_response is not None
            and error.category is not ModelFailureCategory.SAFETY_POLICY_BLOCKED
            and self._retain_raw(raw_response)
        )
        self._invocations.append(
            InvocationRecord(
                provenance=provenance,
                succeeded=False,
                failure_category=error.category.value,
                response_sha256=(sha256_value(raw_response) if raw_response is not None else None),
                raw_response=raw_response if retain else None,
                raw_response_retained=retain,
            )
        )

    def _record_success(
        self,
        *,
        provenance: InvocationProvenance,
        raw_response: str,
    ) -> None:
        retain = self._retain_raw(raw_response)
        self._invocations.append(
            InvocationRecord(
                provenance=provenance,
                succeeded=True,
                response_sha256=sha256_value(raw_response),
                raw_response=raw_response if retain else None,
                raw_response_retained=retain,
            )
        )

    @staticmethod
    def _status_error(response: TransportResponse) -> ModelRunnerError | None:
        if response.status_code == 429:
            return RateLimitError("provider rate limit")
        if response.status_code in {408, 504}:
            return ProviderTimeoutError("provider request timed out")
        if 500 <= response.status_code <= 599:
            return ProviderUnavailableError(
                f"provider unavailable with HTTP {response.status_code}"
            )
        if not 200 <= response.status_code <= 299:
            return ProviderRequestError(
                f"provider rejected request with HTTP {response.status_code}"
            )
        return None

    def _cache_key(
        self,
        *,
        request: TransportRequest,
        model_input: ModelInput,
        prompt: RenderedPrompt,
        stage: ModelStage,
        seed: int,
    ) -> str:
        return SafeResponseCache.make_key(
            {
                "adapter_config_sha256": self.config_sha256,
                "input_sha256": sha256_value(model_input),
                "model_id": self.model_id,
                "prompt_sha256": prompt.sha256,
                "provider": self.provider.value,
                "request": request.model_dump(mode="json", exclude={"headers"}),
                "revision": self.revision,
                "seed": seed,
                "stage": stage.value,
            }
        )

    def _invoke_text(
        self,
        *,
        model_input: ModelInput,
        prompt: RenderedPrompt,
        stage: ModelStage,
        seed: int,
    ) -> str:
        request = self._build_request(prompt, seed=seed)
        cache_key = self._cache_key(
            request=request,
            model_input=model_input,
            prompt=prompt,
            stage=stage,
            seed=seed,
        )
        if self.config.cache.enabled and self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                response = TransportResponse(status_code=cached.status_code, body=cached.body)
                extracted = self._extract_and_validate(response)
                provenance = self._provenance(
                    model_input=model_input,
                    prompt=prompt,
                    stage=stage,
                    seed=seed,
                    attempt=1,
                    cache_key=cache_key,
                    cache_hit=True,
                    usage=extracted.usage,
                )
                self._record_success(provenance=provenance, raw_response=response.body)
                return extracted.text

        attempts = self.config.retry.max_transport_retries + 1
        last_error: ModelRunnerError | None = None
        for attempt in range(1, attempts + 1):
            provenance = self._provenance(
                model_input=model_input,
                prompt=prompt,
                stage=stage,
                seed=seed,
                attempt=attempt,
                cache_key=cache_key,
                cache_hit=False,
            )
            try:
                response = self.transport.send(
                    request, timeout_seconds=self.config.inference.timeout_seconds
                )
            except TimeoutError:
                error = ProviderTimeoutError("provider transport timed out")
                self._record_failure(provenance=provenance, error=error)
                last_error = error
                if attempt < attempts:
                    continue
                break
            status_error = self._status_error(response)
            if status_error is not None:
                self._record_failure(
                    provenance=provenance,
                    error=status_error,
                    raw_response=response.body,
                )
                last_error = status_error
                if status_error.retryable and attempt < attempts:
                    continue
                if not status_error.retryable:
                    raise status_error
                break
            try:
                extracted = self._extract_and_validate(response)
            except ModelRunnerError as exc:
                self._record_failure(provenance=provenance, error=exc, raw_response=response.body)
                raise
            provenance = self._provenance(
                model_input=model_input,
                prompt=prompt,
                stage=stage,
                seed=seed,
                attempt=attempt,
                cache_key=cache_key,
                cache_hit=False,
                usage=extracted.usage,
            )
            self._record_success(provenance=provenance, raw_response=response.body)
            if (
                self.config.cache.enabled
                and self.config.cache.preserve_raw_responses
                and self.cache is not None
            ):
                self.cache.put(
                    cache_key,
                    status_code=response.status_code,
                    body=response.body,
                    retention_policy=self.retention_policy,
                )
            return extracted.text
        cause = last_error.category if last_error is not None else None
        raise RetryExhaustedError(
            "bounded provider retries were exhausted",
            cause_category=cause,
        )

    def _extract_and_validate(self, response: TransportResponse) -> ExtractedProviderResponse:
        extracted = self._extract_response(response)
        if extracted.model_id != self.model_id or extracted.revision != self.revision:
            raise ModelIdentityError(
                "provider response identity does not match the frozen model and revision"
            )
        if not extracted.text:
            raise ProviderResponseError("provider returned empty model text")
        return extracted

    def _action_with_single_repair(
        self,
        model_input: ModelInput,
        *,
        seed: int,
    ) -> ActionOutput:
        prompt = self.prompts.render_action(model_input)
        raw = self._invoke_text(
            model_input=model_input,
            prompt=prompt,
            stage=ModelStage.ACTION,
            seed=seed,
        )
        try:
            return parse_action_output(raw, model_input)
        except (InvalidJSONError, OutputSchemaError) as first_error:
            repair = self.prompts.render_repair(
                invalid_response=raw,
                output_model=ActionOutput,
                original_stage="action",
            )
            repaired = self._invoke_text(
                model_input=model_input,
                prompt=repair,
                stage=ModelStage.ACTION_REPAIR,
                seed=seed,
            )
            try:
                return parse_action_output(repaired, model_input)
            except ModelOutputError as second_error:
                raise InvalidRunError(
                    "action output remained invalid after one deterministic repair",
                    cause_category=second_error.category,
                ) from first_error

    def select_action_input(self, model_input: ModelInput, *, seed: int) -> ActionSelection:
        """Select from the rich contract; used by future memory/intervention hooks."""

        output = self._action_with_single_repair(model_input, seed=seed)
        decision_id = sha256_value(
            {
                "action_output": output.model_dump(mode="json"),
                "config_sha256": self.config_sha256,
                "input_sha256": sha256_value(model_input),
                "seed": seed,
            }
        )
        selection = ActionSelection(
            decision_id=decision_id,
            chosen_action=output.chosen_action_id,
            resources_spent=output.resources_spent,
            retrieved_memory_ids=output.retrieved_memory_ids,
            belief_updates=tuple(
                BeliefUpdate(
                    belief_id=update.belief_id,
                    value=update.value,
                    confidence=update.confidence,
                    evidence_ids=list(update.evidence_ids),
                )
                for update in output.belief_updates
            ),
        )
        self._selection_inputs[decision_id] = model_input
        return selection

    def select_action(self, request: DecisionRequest, *, seed: int) -> ActionSelection:
        return self.select_action_input(self.input_from_request(request), seed=seed)

    def _language_with_single_repair(
        self,
        *,
        model_input: ModelInput,
        chosen_action_id: str,
        action_commitment_sha256: str,
        seed: int,
    ) -> PublicLanguageOutput:
        prompt = self.prompts.render_language(
            model_input,
            chosen_action_id=chosen_action_id,
            action_commitment_sha256=action_commitment_sha256,
        )
        raw = self._invoke_text(
            model_input=model_input,
            prompt=prompt,
            stage=ModelStage.PUBLIC_LANGUAGE,
            seed=seed,
        )
        try:
            return parse_public_language_output(raw)
        except (InvalidJSONError, OutputSchemaError) as first_error:
            repair = self.prompts.render_repair(
                invalid_response=raw,
                output_model=PublicLanguageOutput,
                original_stage="public_language",
            )
            repaired = self._invoke_text(
                model_input=model_input,
                prompt=repair,
                stage=ModelStage.PUBLIC_LANGUAGE_REPAIR,
                seed=seed,
            )
            try:
                return parse_public_language_output(repaired)
            except ModelOutputError as second_error:
                raise InvalidRunError(
                    "public language remained invalid after one deterministic repair",
                    cause_category=second_error.category,
                ) from first_error

    def generate_public_language(
        self,
        request: DecisionRequest,
        selection: ActionSelection,
        *,
        action_commitment_sha256: str,
        seed: int,
    ) -> str:
        try:
            model_input = self._selection_inputs[selection.decision_id]
        except KeyError as exc:
            raise ProviderRequestError(
                "public language requires an action selected by this adapter instance"
            ) from exc
        if model_input.request_id != request.request_id:
            raise ProviderRequestError("public-language request differs from action-stage input")
        output = self._language_with_single_repair(
            model_input=model_input,
            chosen_action_id=selection.chosen_action,
            action_commitment_sha256=action_commitment_sha256,
            seed=seed,
        )
        return output.public_response

    def decide(self, request: DecisionRequest, *, seed: int) -> ModelDecision:
        """Legacy one-call compatibility; simulation should use the two-stage methods."""

        selection = self.select_action(request, seed=seed)
        commitment = sha256_value(
            {
                "decision_id": selection.decision_id,
                "legacy_compatibility": True,
                "request_id": request.request_id,
            }
        )
        public_response = self.generate_public_language(
            request,
            selection,
            action_commitment_sha256=commitment,
            seed=seed,
        )
        return ModelDecision(
            schema_version="1.0",
            decision_id=selection.decision_id,
            chosen_action=selection.chosen_action,
            resources_spent=selection.resources_spent,
            retrieved_memory_ids=list(selection.retrieved_memory_ids),
            belief_updates=list(selection.belief_updates),
            public_response=public_response,
        )


MALFORMED_OUTPUT_CATEGORIES = frozenset(
    {ModelFailureCategory.INVALID_JSON, ModelFailureCategory.OUTPUT_SCHEMA_MISMATCH}
)
