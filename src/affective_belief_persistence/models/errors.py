"""Normalized model-runner failures and retry policy metadata."""

from __future__ import annotations

from enum import StrEnum


class ModelFailureCategory(StrEnum):
    INVALID_JSON = "invalid_json"
    OUTPUT_SCHEMA_MISMATCH = "output_schema_mismatch"
    INVALID_ACTION = "invalid_action"
    COST_MISMATCH = "cost_mismatch"
    UNKNOWN_MEMORY_REFERENCE = "unknown_memory_reference"
    MALFORMED_OUTPUT_UNREPAIRED = "malformed_output_unrepaired"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_REQUEST_REJECTED = "provider_request_rejected"
    PROVIDER_RESPONSE_INVALID = "provider_response_invalid"
    MODEL_IDENTITY_MISMATCH = "model_identity_mismatch"
    RETRY_EXHAUSTED = "retry_exhausted"
    CACHE_CORRUPT = "cache_corrupt"
    SAFETY_POLICY_BLOCKED = "safety_policy_blocked"


class ModelRunnerError(RuntimeError):
    """Base exception exposing a stable category and retryability flag."""

    category = ModelFailureCategory.PROVIDER_RESPONSE_INVALID
    retryable = False

    def __init__(self, message: str, *, cause_category: ModelFailureCategory | None = None) -> None:
        super().__init__(message)
        self.cause_category = cause_category


class ModelOutputError(ModelRunnerError):
    """Provider text cannot be accepted as a structured model output."""


class InvalidJSONError(ModelOutputError):
    category = ModelFailureCategory.INVALID_JSON


class OutputSchemaError(ModelOutputError):
    category = ModelFailureCategory.OUTPUT_SCHEMA_MISMATCH


class InvalidActionError(ModelOutputError):
    category = ModelFailureCategory.INVALID_ACTION


class CostMismatchError(ModelOutputError):
    category = ModelFailureCategory.COST_MISMATCH


class UnknownMemoryReferenceError(ModelOutputError):
    category = ModelFailureCategory.UNKNOWN_MEMORY_REFERENCE


class InvalidRunError(ModelRunnerError):
    category = ModelFailureCategory.MALFORMED_OUTPUT_UNREPAIRED


class ProviderTimeoutError(ModelRunnerError):
    category = ModelFailureCategory.TIMEOUT
    retryable = True


class RateLimitError(ModelRunnerError):
    category = ModelFailureCategory.RATE_LIMIT
    retryable = True


class ProviderUnavailableError(ModelRunnerError):
    category = ModelFailureCategory.PROVIDER_UNAVAILABLE
    retryable = True


class ProviderRequestError(ModelRunnerError):
    category = ModelFailureCategory.PROVIDER_REQUEST_REJECTED


class ProviderResponseError(ModelRunnerError):
    category = ModelFailureCategory.PROVIDER_RESPONSE_INVALID


class ModelIdentityError(ModelRunnerError):
    category = ModelFailureCategory.MODEL_IDENTITY_MISMATCH


class RetryExhaustedError(ModelRunnerError):
    category = ModelFailureCategory.RETRY_EXHAUSTED


class CacheCorruptionError(ModelRunnerError):
    category = ModelFailureCategory.CACHE_CORRUPT


class SafetyPolicyError(ModelRunnerError):
    category = ModelFailureCategory.SAFETY_POLICY_BLOCKED
