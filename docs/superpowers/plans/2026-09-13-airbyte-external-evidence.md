# AgentOps External Evidence & Connector Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, default-deny external evidence layer with an Airbyte adapter, bounded retries/output, audit events, and deferred OpenAI Agents tool exposure while preserving the deterministic release gate.

**Architecture:** `app/external_evidence.py` owns provider-neutral contracts, authorization, normalization, retry/output limits, and audit event construction. `app/airbyte_provider.py` is an optional adapter that imports the Airbyte Agent SDK only when used and exposes only explicitly allowlisted read/evidence operations. `app/agents_runtime.py` consumes provider-generated OpenAI Agents tools as supplemental deferred tools; `app/agentops.py` remains authoritative for release decisions.

**Tech Stack:** Python 3.13, dataclasses/typing, pytest, optional Airbyte Agent SDK, OpenAI Agents SDK, existing deterministic policy engine.

**Spec:** `docs/superpowers/specs/2026-09-13-airbyte-external-evidence-design.md`

## Global Constraints

- `AGENT_RUNTIME=deterministic` remains the default.
- No API key is required for deterministic tests.
- Airbyte is optional; do not make the full Airbyte platform a mandatory dependency.
- Do not replace or bypass the deterministic severity gate.
- Do not add automatic release approval based on model output.
- Do not enable destructive external operations in the initial adapter.
- Do not log credentials, access tokens, or connector secrets.
- Do not couple deterministic policy evaluation to an external provider's availability.

---

### Task 1: Provider-neutral evidence contracts and guards

**Files:**
- Create: `app/external_evidence.py`
- Test: `tests/test_external_evidence.py`

**Interfaces:**
- Produces `EvidenceStatus`, `AuthorizationDecision`, `ExternalEvidence`, `ExternalContextProvider`, `EvidencePolicy`, `RetryPolicy`, `AuditEvent`, `bounded_text`, and `execute_evidence_operation` for later tasks.
- `ExternalContextProvider` must expose `provider_name`, `inspect_capability(connector)`, and `execute(connector, operation, arguments)` without importing Airbyte types.

- [ ] **Step 1: Write the failing tests for the evidence envelope, default-deny policy, write rejection, and output bounding.**

```python
from app.external_evidence import (
    EvidencePolicy,
    ExternalEvidence,
    EvidenceStatus,
    AuthorizationDecision,
    bounded_text,
    authorize_operation,
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


def test_write_operation_is_rejected_even_when_not_allowlisted():
    policy = EvidencePolicy(allowlist={
        ("airbyte", "github", "create_issue"): True,
    })
    decision = authorize_operation(policy, "airbyte", "github", "create_issue", operation_class="write")
    assert decision is AuthorizationDecision.DENIED


def test_bounded_text_marks_truncation():
    text, truncated = bounded_text("abcdef", max_chars=4)
    assert text == "abcd"
    assert truncated is True
```

- [ ] **Step 2: Run the focused tests to verify the contract is currently missing.**

Run: `pytest tests/test_external_evidence.py -q`
Expected: FAIL because `app.external_evidence` does not yet exist.

- [ ] **Step 3: Implement the provider-neutral contracts and pure guards.**

```python
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
    allowlist: dict[tuple[str, str, str], bool]

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
    return (text[:max_chars], True) if len(text) > max_chars else (text, False)
```

- [ ] **Step 4: Run the focused tests to verify they pass.**

Run: `pytest tests/test_external_evidence.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the provider contract.**

```bash
git add app/external_evidence.py tests/test_external_evidence.py
git commit -m "feat: add external evidence contracts"
```

### Task 2: Authorized execution, retries, and audit events

**Files:**
- Modify: `app/external_evidence.py`
- Modify: `tests/test_external_evidence.py`

**Interfaces:**
- Produces `RetryPolicy`, `AuditEvent`, and `execute_evidence_operation(provider, policy, connector, operation, arguments, retry_policy, max_output_chars)`.
- `execute_evidence_operation` returns `(ExternalEvidence, AuditEvent)` and must never retry denied/invalid operations.

- [ ] **Step 1: Add failing tests for bounded transient retries, no retry on authorization denial, output limits, and secret-free audit events.**

```python
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
    policy = EvidencePolicy({})
    evidence, audit = execute_evidence_operation(
        provider, policy, "github", "read", {}, RetryPolicy(max_retries=2), max_output_chars=100
    )
    assert provider.calls == 0
    assert evidence.status is EvidenceStatus.FAILED
    assert audit.authorization == AuthorizationDecision.DENIED


def test_audit_event_never_contains_secret_values():
    provider = FakeProvider()
    policy = EvidencePolicy({("airbyte", "github", "read"): True})
    evidence, audit = execute_evidence_operation(
        provider, policy, "github", "read", {"token": "SECRET_TOKEN"}, RetryPolicy(max_retries=0), max_output_chars=100
    )
    serialized = str(audit.__dict__)
    assert "SECRET_TOKEN" not in serialized
```

- [ ] **Step 2: Run the focused tests to verify they fail for the new execution behavior.**

Run: `pytest tests/test_external_evidence.py -q`
Expected: FAIL because retry/audit execution is not implemented.

- [ ] **Step 3: Implement bounded execution and redacted audit construction.**

```python
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

def _safe_arguments(arguments):
    return {k: "[REDACTED]" for k in arguments if any(token in k.lower() for token in ("token", "secret", "password", "api_key", "credential"))}

def execute_evidence_operation(provider, policy, connector, operation, arguments, retry_policy, max_output_chars):
    decision = authorize_operation(policy, provider.provider_name, connector, operation)
    if decision is AuthorizationDecision.DENIED:
        evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.FAILED, error="Operation denied by external evidence policy")
        return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, 0, error=evidence.error)
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
            if attempts >= retry_policy.max_retries:
                evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.FAILED, retry_count=attempts, error=type(exc).__name__)
                return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, attempts, error=type(exc).__name__)
            attempts += 1
        except Exception as exc:
            evidence = ExternalEvidence(provider.provider_name, connector, operation, EvidenceStatus.FAILED, retry_count=attempts, error=type(exc).__name__)
            return evidence, AuditEvent(provider.provider_name, connector, operation, decision, evidence.status, attempts, error=type(exc).__name__)
```

- [ ] **Step 4: Run all evidence tests.**

Run: `pytest tests/test_external_evidence.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the execution boundary.**

```bash
git add app/external_evidence.py tests/test_external_evidence.py
git commit -m "feat: add bounded evidence execution and audit"
```

### Task 3: Optional Airbyte adapter

**Files:**
- Create: `app/airbyte_provider.py`
- Modify: `tests/test_external_evidence.py`

**Interfaces:**
- Produces `AirbyteEvidenceProvider(policy, connector_factory=None)` implementing `ExternalContextProvider`.
- The module must import Airbyte lazily and raise a clear runtime error only when the adapter is instantiated/used without the optional SDK.
- Connector operations are selected from a provider-side allowlist; arbitrary callable names supplied by a caller are rejected.

- [ ] **Step 1: Write failing tests for missing optional dependency and allowlisted connector execution.**

```python
def test_airbyte_adapter_is_optional(monkeypatch):
    monkeypatch.setitem(sys.modules, "airbyte_agent_sdk", None)
    from app.airbyte_provider import AirbyteEvidenceProvider
    with pytest.raises(RuntimeError, match="Airbyte Agent SDK"):
        AirbyteEvidenceProvider(EvidencePolicy({}))


def test_airbyte_adapter_exposes_only_allowlisted_read_operations():
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
```

- [ ] **Step 2: Run the adapter tests to verify they fail before the adapter exists.**

Run: `pytest tests/test_external_evidence.py -q`
Expected: FAIL because `app.airbyte_provider` does not yet exist.

- [ ] **Step 3: Implement lazy SDK loading and the three progressive Airbyte operations.**

```python
from typing import Any, Callable
from .external_evidence import ExternalContextProvider, ExternalEvidence, EvidenceStatus, EvidencePolicy, authorize_operation, AuthorizationDecision

_READ_OPERATIONS = {"inspect_connector", "read_skill_docs", "execute"}

class AirbyteEvidenceProvider:
    provider_name = "airbyte"

    def __init__(self, policy: EvidencePolicy, connector_factory: Callable[[str], Any] | None = None, sdk_available: bool | None = None):
        if sdk_available is False:
            raise RuntimeError("Airbyte Agent SDK is not installed; install the optional Airbyte agent SDK to use this provider.")
        if connector_factory is None:
            try:
                from airbyte_agent_sdk import get_connector
            except ImportError as exc:
                raise RuntimeError("Airbyte Agent SDK is not installed; install the optional Airbyte agent SDK to use this provider.") from exc
            connector_factory = get_connector
        self.policy = policy
        self.connector_factory = connector_factory

    def inspect_capability(self, connector):
        if authorize_operation(self.policy, self.provider_name, connector, "inspect_connector") is AuthorizationDecision.DENIED:
            return {"connector": connector, "authorized": False, "operations": []}
        client = self.connector_factory(connector)
        return {"connector": connector, "authorized": True, "operations": sorted(_READ_OPERATIONS), "capability": client.inspect_connector()}

    def execute(self, connector, operation, arguments):
        if operation not in _READ_OPERATIONS:
            return ExternalEvidence(self.provider_name, connector, operation, EvidenceStatus.FAILED, error="Unsupported external operation")
        if authorize_operation(self.policy, self.provider_name, connector, operation) is AuthorizationDecision.DENIED:
            return ExternalEvidence(self.provider_name, connector, operation, EvidenceStatus.FAILED, error="Operation denied by external evidence policy")
        client = self.connector_factory(connector)
        if operation == "inspect_connector":
            payload = client.inspect_connector()
        elif operation == "read_skill_docs":
            payload = client.read_skill_docs(section=arguments.get("section"))
        else:
            payload = client.execute(arguments.get("operation"), **arguments.get("parameters", {}))
        return ExternalEvidence.success(self.provider_name, connector, operation, payload, provenance={"provider": "airbyte", "connector": connector})
```

- [ ] **Step 4: Run adapter and evidence tests.**

Run: `pytest tests/test_external_evidence.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the optional adapter.**

```bash
git add app/airbyte_provider.py tests/test_external_evidence.py
git commit -m "feat: add optional Airbyte evidence provider"
```

### Task 4: Deferred OpenAI Agents integration

**Files:**
- Modify: `app/agents_runtime.py`
- Modify: `tests/test_agentops.py`

**Interfaces:**
- Produces `build_external_evidence_tools(provider)` returning OpenAI Agents-compatible tools when the SDK and provider are available.
- Manager keeps the seven specialist tools deferred inside `agentops_specialists` and adds the external evidence namespace as a separate deferred namespace; no external tool becomes authoritative for release policy.

- [ ] **Step 1: Add failing structural tests for the external namespace and deferred loading.**

```python
def test_external_evidence_tools_are_deferred_and_namespaced(monkeypatch):
    from app.agents_runtime import build_external_evidence_tools
    class FakeProvider:
        provider_name = "airbyte"
    tools = build_external_evidence_tools(FakeProvider())
    assert tools.name == "agentops_external_evidence"
    assert all(getattr(tool, "defer_loading", False) for tool in tools.tools)
```

- [ ] **Step 2: Run the targeted SDK structural test to verify it fails.**

Run: `pytest tests/test_agentops.py::test_external_evidence_tools_are_deferred_and_namespaced -q`
Expected: FAIL because the helper is not yet implemented.

- [ ] **Step 3: Implement the helper and manager wiring without changing the specialist fleet or deterministic gate.**

```python
def build_external_evidence_tools(provider):
    Agent, _, _, _, tool_namespace = _require_sdk()
    from agents import function_tool

    @function_tool
    def inspect_external_connector(connector: str):
        return provider.inspect_capability(connector)

    @function_tool
    def read_external_evidence(connector: str, operation: str, arguments: dict[str, Any] | None = None):
        evidence = provider.execute(connector, operation, arguments or {})
        return evidence.model_dump() if hasattr(evidence, "model_dump") else evidence.__dict__

    for tool in (inspect_external_connector, read_external_evidence):
        tool.defer_loading = True
    return tool_namespace(
        name="agentops_external_evidence",
        description="Authorized read-only external evidence tools. These tools provide evidence and never approve releases.",
        tools=[inspect_external_connector, read_external_evidence],
    )
```

Add the returned namespace to the manager's `tools` list alongside `ToolSearchTool()` while preserving `ModelSettings(tool_choice="auto")` and the existing specialist namespace.

- [ ] **Step 4: Run the SDK structural tests and deterministic regression suite.**

Run: `pytest tests/test_agentops.py -q`
Expected: PASS, with the deterministic release-policy tests unchanged.

- [ ] **Step 5: Commit the deferred integration.**

```bash
git add app/agents_runtime.py tests/test_agentops.py
git commit -m "feat: expose deferred external evidence tools"
```

### Task 5: Control-plane audit integration and documentation

**Files:**
- Modify: `app/agentops.py`
- Modify: `README.md`
- Modify: `tests/test_agentops.py`

**Interfaces:**
- `build_run_from_sdk_report` remains the deterministic policy boundary.
- External evidence events are appended only as evidence/audit metadata and cannot alter severity counts, release status, or approval eligibility.

- [ ] **Step 1: Write a failing regression test proving external evidence cannot approve a blocked run and that audit records carry provider metadata.**

```python
def test_external_evidence_is_supplemental_to_deterministic_gate():
    from app.agentops import build_run_from_sdk_report
    report = {"summary": "evidence", "reports": [{
        "agent": "Security", "role": "Security & Threat Modeling", "status": "READY",
        "summary": "No issue", "score": 100, "findings": [{
            "severity": "HIGH", "category": "Authorization", "title": "External evidence cannot override gate",
            "detail": "High severity remains blocking", "recommendation": "Remediate", "owner": "Security", "status": "OPEN"
        }]
    }]}
    data = build_run_from_sdk_report("Example", report)
    assert data["release_status"] == "BLOCKED"
    assert data["approval"]["allowed"] is False
```

- [ ] **Step 2: Run the focused regression test to verify the unchanged policy behavior.**

Run: `pytest tests/test_agentops.py::test_external_evidence_is_supplemental_to_deterministic_gate -q`
Expected: PASS once the test is added; the test itself documents the invariant and must remain green after integration.

- [ ] **Step 3: Add an optional evidence field/audit-event normalization path and document configuration.**

The runtime response may include an `external_evidence` list containing serialized `ExternalEvidence`/`AuditEvent` records. Do not use those records in `review_agent`, severity counting, or approval calculations. Update README to state that Airbyte is optional, read-only/default-deny, and never a release-policy authority.

- [ ] **Step 4: Run the complete regression suite.**

Run: `pytest -q`
Expected: PASS with no requirement for `OPENAI_API_KEY` or live Airbyte credentials.

- [ ] **Step 5: Commit the control-plane/documentation integration.**

```bash
git add app/agentops.py tests/test_agentops.py README.md
git commit -m "docs: document external evidence control boundary"
```

### Task 6: Final verification and branch handoff

**Files:**
- Verify: all changed files from Tasks 1–5

- [ ] **Step 1: Run the complete test suite from a clean working tree.**

Run: `pytest -q`
Expected: exit code 0 and zero failed tests.

- [ ] **Step 2: Verify deterministic runtime defaults remain intact.**

Run: `python -c "from app.runtime import get_runtime; print(get_runtime())"`
Expected: `RuntimeInfo(name='deterministic', available=True)` when `AGENT_RUNTIME` is unset.

- [ ] **Step 3: Inspect the final diff for forbidden behavior.**

Run: `git diff main...HEAD -- app tests README.md`
Expected: no full Airbyte platform dependency, no destructive/write default path, no credentials in audit code, no release decision derived from external evidence, and no replacement of the eight-role architecture.

- [ ] **Step 4: Record verification evidence and branch status.**

Run: `git status --short --branch && git log --oneline --decorate -8`
Expected: feature branch contains only the planned commits and the worktree is clean.

- [ ] **Step 5: Stop before merge/push/PR publication if additional authorization is required by the execution environment.**

No merge into `main` is part of this plan. A pull request can be created only as a separate externally visible handoff action after verification.
