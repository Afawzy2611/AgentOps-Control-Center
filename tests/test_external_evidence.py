import pytest

from app.external_evidence import (
    AuthorizationDecision,
    EvidencePolicy,
    EvidenceStatus,
    ExternalEvidence,
    authorize_operation,
    bounded_text,
)


def test_evidence_envelope_contains_required_metadata():
    evidence = ExternalEvidence.success(
        provider="airbyte",
        connector="github",
        operation="search_issues",
        payload={"items": [1]},
        provenance={"source": "github"},
        retry_count=1,
    )
    assert evidence.provider == "airbyte"
    assert evidence.connector == "github"
    assert evidence.operation == "search_issues"
    assert evidence.status is EvidenceStatus.SUCCESS
    assert evidence.retry_count == 1
    assert evidence.truncated is False


def test_authorization_defaults_to_deny():
    policy = EvidencePolicy(allowlist={})
    decision = authorize_operation(policy, "airbyte", "github", "search_issues")
    assert decision is AuthorizationDecision.DENIED


def test_write_operation_is_rejected_even_when_allowlisted():
    policy = EvidencePolicy({("airbyte", "github", "create_issue"): True})
    decision = authorize_operation(
        policy,
        "airbyte",
        "github",
        "create_issue",
        operation_class="write",
    )
    assert decision is AuthorizationDecision.DENIED


def test_bounded_text_marks_truncation():
    text, truncated = bounded_text("abcdef", max_chars=4)
    assert text == "abcd"
    assert truncated is True
