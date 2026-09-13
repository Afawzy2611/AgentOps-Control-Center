import sys
from types import SimpleNamespace

import pytest

from app.external_evidence import (
    AuthorizationDecision,
    EvidencePolicy,
    EvidenceStatus,
    ExternalEvidence,
    RetryPolicy,
    authorize_operation,
    bounded_text,
    execute_evidence_operation,
)


def test_evidence_envelope_contains_required_metadata():
    evidence = ExternalEvidence.success(
        provider="airbyte", connector="github", operation="search_issues",
        payload={"items": [1]}, provenance={"source": "github"}, retry_count=1,
    )
    assert evidence.provider == "airbyte"
    assert evidence.connector == "github"
    assert evidence.operation == "search_issues"
    assert evidence.status is EvidenceStatus.SUCCESS
    assert evidence.retry_count == 1
    assert evidence.truncated is False


def test_authorization_defaults_to_deny():
    policy = EvidencePolicy(allowlist={})
    assert authorize_operation(policy, "airbyte", "github", "search_issues") is AuthorizationDecision.DENIED


def test_write_operation_is_rejected_even_when_allowlisted():
    policy = EvidencePolicy({("airbyte", "github", "create_issue"): True})
    assert authorize_operation(policy, "airbyte", "github", "create_issue", operation_class="write") is AuthorizationDecision.DENIED


def test_bounded_text_marks_truncation():
    text, truncated = bounded_text("abcdef", max_chars=4)
    assert text == "abcd"
    assert truncated is True


class FakeProvider:
    provider_name = "airbyte"

    def __init__(self):
        self.calls = 0

    def inspect_capability(self, connector):
        return {"connector": connector, "operations": ["read"]}

    def execute(self, connector, operation, arguments):
        self.calls += 1
        if self.calls < 3:
            raise TimeoutError("temporary timeout")
        return ExternalEvidence.success("airbyte", connector, operation, "abcdefgh")


def test_transient_failures_are_retried_with_a_bounded_count():
    provider = FakeProvider()
    policy = EvidencePolicy({("airbyte", "github", "read"): True})
    evidence, audit = execute_evidence_operation(
        provider, policy, "github", "read", {}, RetryPolicy(max_retries=2), max_output_chars=4
    )
    assert provider.calls == 3
    assert evidence.retry_count == 2
    assert evidence.truncated is True
    assert audit.retry_count == 2


def test_denied_operation_is_not_retried():
    provider = FakeProvider()
    evidence, audit = execute_evidence_operation(
        provider, EvidencePolicy({}), "github", "read", {}, RetryPolicy(max_retries=2), max_output_chars=100
    )
    assert provider.calls == 0
    assert evidence.status is EvidenceStatus.FAILED
    assert audit.authorization is AuthorizationDecision.DENIED


def test_audit_event_never_contains_secret_values():
    provider = FakeProvider()
    policy = EvidencePolicy({("airbyte", "github", "read"): True})
    _, audit = execute_evidence_operation(
        provider, policy, "github", "read", {"token": "SECRET_TOKEN"}, RetryPolicy(max_retries=0), max_output_chars=100
    )
    assert "SECRET_TOKEN" not in str(audit.__dict__)
    assert audit.provenance["redacted_arguments"]["token"] == "[REDACTED]"


def test_airbyte_adapter_is_optional(monkeypatch):
    monkeypatch.setitem(sys.modules, "airbyte_agent_sdk", None)
    from app.airbyte_provider import AirbyteEvidenceProvider
    with pytest.raises(RuntimeError, match="Airbyte Agent SDK"):
        AirbyteEvidenceProvider(EvidencePolicy({}))


def test_airbyte_adapter_exposes_only_allowlisted_read_operations():
    from app.airbyte_provider import AirbyteEvidenceProvider

    class FakeConnector:
        def inspect_connector(self):
            return {"name": "github"}

        def read_skill_docs(self, section=None):
            return "skill docs"

        def execute(self, operation, **kwargs):
            return {"operation": operation, "items": []}

    provider = AirbyteEvidenceProvider(
        EvidencePolicy({
            ("airbyte", "github", "inspect_connector"): True,
            ("airbyte", "github", "read_skill_docs"): True,
            ("airbyte", "github", "execute"): True,
        }),
        connector_factory=lambda name: FakeConnector(),
        sdk_available=True,
    )
    assert provider.inspect_capability("github")["connector"] == "github"
    evidence = provider.execute("github", "inspect_connector", {})
    assert evidence.status is EvidenceStatus.SUCCESS


def test_airbyte_adapter_rejects_unknown_operation():
    from app.airbyte_provider import AirbyteEvidenceProvider

    provider = AirbyteEvidenceProvider(
        EvidencePolicy({("airbyte", "github", "execute"): True}),
        connector_factory=lambda name: SimpleNamespace(),
        sdk_available=True,
    )
    evidence = provider.execute("github", "delete_repository", {})
    assert evidence.status is EvidenceStatus.FAILED
    assert evidence.error == "Unsupported external operation"
