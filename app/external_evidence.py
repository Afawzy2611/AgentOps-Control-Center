"""Provider-neutral external evidence contracts and safety boundaries."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class EvidenceStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AuthorizationDecision(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class ExternalEvidence:
    provider: str
    connector: str
    operation: str
    status: EvidenceStatus
    payload: Any = None
    provenance: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retry_count: int = 0
    truncated: bool = False
    error: str | None = None

    @classmethod
    def success(cls, provider, connector, operation, payload, provenance=None, retry_count=0, truncated=False):
        return cls(provider, connector, operation, EvidenceStatus.SUCCESS, payload, provenance or {}, retry_count=retry_count, truncated=truncated)


@dataclass(frozen=True)
class EvidencePolicy:
    allowlist: dict[tuple[str, str, str], bool] = field(default_factory=dict)


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    retryable_exceptions: tuple[type[Exception], ...] = (TimeoutError, ConnectionError)


@dataclass(frozen=True)
class AuditEvent:
    provider: str
    connector: str
    operation: str
    authorization: AuthorizationDecision
    status: EvidenceStatus
    retry_count: int
    provenance: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    error: str | None = None


class ExternalContextProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    def inspect_capability(self, connector: str) -> dict[str, Any]: ...

    def execute(self, connector: str, operation: str, arguments: dict[str, Any]) -> ExternalEvidence: ...


def authorize_operation(policy, provider, connector, operation, operation_class="read"):
    if operation_class != "read":
        return AuthorizationDecision.DENIED
    return AuthorizationDecision.ALLOWED if policy.allowlist.get((provider, connector, operation), False) else AuthorizationDecision.DENIED


def bounded_text(value, max_chars=100_000):
    text = value if isinstance(value, str) else str(value)
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, False


def _redacted_arguments(arguments):
    secret_tokens = ("token", "secret", "password", "api_key", "apikey", "credential")
    return {key: "[REDACTED]" for key in arguments if any(token in key.lower() for token in secret_tokens)}


def execute_evidence_operation(provider, policy, connector, operation, arguments, retry_policy, max_output_chars=100_000):
    decision = authorize_operation(policy, provider.provider_name, connector, operation)
    if decision is AuthorizationDecision.DENIED:
        evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.FAILED, error="Operation denied by external evidence policy")
        return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, 0, provenance={"redacted_arguments": _redacted_arguments(arguments)}, error=evidence.error)

    attempts = 0
    while True:
        try:
            evidence = provider.execute(connector, operation, arguments)
            payload = evidence.payload
            truncated = evidence.truncated
            if isinstance(payload, str):
                payload, truncated = bounded_text(payload, max_output_chars)
            evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.SUCCESS, payload, evidence.provenance, retry_count=attempts, truncated=truncated)
            return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, attempts, evidence.provenance, truncated=truncated)
        except retry_policy.retryable_exceptions as exc:
            if attempts >= max(0, retry_policy.max_retries):
                error_name = type(exc).__name__
                evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.FAILED, retry_count=attempts, error=error_name)
                return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, attempts, error=error_name)
            attempts += 1
        except Exception as exc:
            error_name = type(exc).__name__
            evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.FAILED, retry_count=attempts, error=error_name)
            return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, attempts, error=error_name)
