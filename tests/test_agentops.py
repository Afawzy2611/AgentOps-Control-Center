from app.agentops import run_demo


def test_all_agents_run():
    data = run_demo()
    assert len(data["agents"]) == 8
    assert {a["agent"] for a in data["agents"]} >= {"Developer", "Security", "QA", "Governance", "Observability", "Review"}


def test_high_finding_blocks_release():
    data = run_demo()
    assert data["release_status"] == "BLOCKED"
    assert data["release_gate"]["passed"] is False
    assert data["release_gate"]["counts"]["HIGH"] >= 1


def test_security_and_qa_surface_authorization_gap():
    data = run_demo()
    titles = {f["title"] for f in data["findings"]}
    assert "Authorization check missing on /api/projects/{id}" in titles
    assert "Add authorization regression test" in titles


def test_recommendations_and_queue_are_generated():
    data = run_demo()
    assert data["recommendations"]
    assert len(data["remediation_queue"]) == len(data["findings"])
    assert all(item["id"].startswith("F-") for item in data["remediation_queue"])


def test_blocked_release_cannot_be_approved():
    data = run_demo()
    assert data["approval"]["allowed"] is False


def test_audit_security_and_policy_metadata():
    data = run_demo()
    assert data["audit_log"]
    assert data["security"]["external_actions_enabled"] is False
    assert data["release_gate"]["thresholds"]["block_on"] == ["CRITICAL", "HIGH"]


def test_runtime_defaults_to_deterministic(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)
    from app.runtime import get_runtime
    runtime = get_runtime()
    assert runtime.name == "deterministic"
    assert runtime.available is True


def test_agents_sdk_runtime_selection_is_explicit(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME", "agents_sdk")
    from app.runtime import get_runtime
    runtime = get_runtime()
    assert runtime.name == "agents_sdk"
    assert isinstance(runtime.available, bool)


def test_agents_sdk_agent_fleet_has_expected_roles():
    from app.agents_runtime import AGENT_ROLES
    assert AGENT_ROLES == [
        "Developer", "Security", "QA", "Data", "Research", "Governance", "Observability", "Review"
    ]


def test_sdk_report_uses_deterministic_policy_gate():
    from app.agentops import build_run_from_sdk_report
    report = {
        "summary": "live manager summary",
        "reports": [
            {
                "agent": "Security",
                "role": "Security & Threat Modeling",
                "status": "REVIEW",
                "summary": "Authorization risk found.",
                "score": 60,
                "findings": [{
                    "severity": "HIGH",
                    "category": "Authorization",
                    "title": "Authorization gap",
                    "detail": "Cross-tenant access risk.",
                    "recommendation": "Enforce tenant authorization.",
                    "owner": "Security",
                    "status": "OPEN"
                }]
            }
        ]
    }
    data = build_run_from_sdk_report("Example", report)
    assert data["runtime"] == "agents_sdk"
    assert data["release_status"] == "BLOCKED"
    assert data["approval"]["allowed"] is False
    assert data["security"]["destructive_actions"] == "disabled"
    assert data["agent_runtime_summary"] == "live manager summary"
