"""Lazy public boundary for the Gate 3 authorization and preflight package."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "GATE3_SCHEMA_MODELS": ".contracts",
    "AuthorizationDecision": ".contracts",
    "BudgetReservation": ".budget",
    "CheckStatus": ".contracts",
    "Gate3Authorization": ".contracts",
    "Gate3Budget": ".contracts",
    "Gate3CallBudgetAmendment": ".contracts",
    "Gate3CredentialReference": ".contracts",
    "Gate3Evidence": ".contracts",
    "GatewayDeploymentManifest": ".contracts",
    "GatewayMetadataSnapshot": ".contracts",
    "GatewayProbeResult": ".contracts",
    "GatewayRuntimeIdentity": ".contracts",
    "GatewaySecurityPolicy": ".contracts",
    "Gate3ModelBinding": ".contracts",
    "Gate3PreflightError": ".preflight",
    "Gate3PreflightResult": ".contracts",
    "Gate3SourceLocks": ".contracts",
    "LivePilotBudgetAccount": ".budget",
    "OfflineRevisionStampingGateway": ".gateway",
    "PilotBudgetExceededError": ".budget",
    "PilotIntegritySummary": ".contracts",
    "PreflightCheck": ".contracts",
    "build_blocked_evidence": ".preflight",
    "collect_source_locks": ".preflight",
    "load_gate3_authorization": ".preflight",
    "load_gate3_call_budget_amendment": ".preflight",
    "load_gateway_manifest": ".gateway",
    "probe_gateway_identity": ".gateway",
    "require_passed_gate3_evidence": ".preflight",
    "run_gate3_preflight": ".preflight",
}

__all__ = tuple(sorted(_EXPORTS))


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
