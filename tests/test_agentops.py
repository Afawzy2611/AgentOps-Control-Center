from types import SimpleNamespace

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
    assert AGENT_ROLES == ["Developer", "Security", "QA", "Data", "Research", "Governance", "Observability", "Review"]


def test_manager_defers_specialist_agent_tools_and_adds_tool_search(monkeypatch):
    import sys
    created = []

    class FakeTool:
        def __init__(self, name):
            self.name = name
            self.defer_loading = False
            self.namespace = None

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.name = kwargs["name"]
            created.append(self)

        def as_tool(self, *, tool_name, tool_description):
            return FakeTool(tool_name)

    class FakeToolSearchTool:
        name = "tool_search"

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def fake_tool_namespace(*, name, description, tools):
        for tool in tools:
            tool.namespace = name
        return tools

    fake_agents = SimpleNamespace(Agent=FakeAgent, Runner=object, ModelSettings=FakeModelSettings, ToolSearchTool=FakeToolSearchTool, tool_namespace=fake_tool_namespace)
    monkeypatch.setitem(sys.modules, "agents", fake_agents)

    from app.agents_runtime import build_manager_agent
    manager = build_manager_agent(model="gpt-5.6")
    tools = manager.kwargs["tools"]
    specialist_tools = [tool for tool in tools if getattr(tool, "name", "") != "tool_search"]
    search_tools = [tool for tool in tools if getattr(tool, "name", "") == "tool_search"]

    assert len(search_tools) == 1
    assert len(specialist_tools) == 7
    assert all(tool.defer_loading is True for tool in specialist_tools)
    assert {tool.namespace for tool in specialist_tools} == {"agentops_specialists"}
    assert manager.kwargs["model_settings"].tool_choice == "auto"
    assert "tool_search" not in str(manager.kwargs.get("instructions", "")).lower() or "load" in manager.kwargs["instructions"].lower()


def test_external_evidence_tools_are_deferred_and_named(monkeypatch):
    import sys

    class FakeTool:
        def __init__(self, name):
            self.name = name
            self.defer_loading = False

    def fake_function_tool(func, **kwargs):
        return FakeTool(kwargs["name_override"])

    monkeypatch.setitem(sys.modules, "agents", SimpleNamespace(function_tool=fake_function_tool))
    from app.agents_runtime import build_external_evidence_tools

    tools = build_external_evidence_tools(SimpleNamespace(), SimpleNamespace(), ["github"])
    assert {tool.name for tool in tools} == {"external_github_inspect_connector", "external_github_read_skill_docs", "external_github_execute"}
    assert all(tool.defer_loading is True for tool in tools)


def test_sdk_report_uses_deterministic_policy_gate():
    from app.agentops import build_run_from_sdk_report
    report = {
        "summary": "live manager summary",
        "reports": [{"agent": "Security", "role": "Security & Threat Modeling", "status": "REVIEW", "summary": "Authorization risk found.", "score": 60, "findings": [{"severity": "HIGH", "category": "Authorization", "title": "Authorization gap", "detail": "Cross-tenant access risk.", "recommendation": "Enforce tenant authorization.", "owner": "Security", "status": "OPEN"}]}]
    }
    data = build_run_from_sdk_report("Example", report)
    assert data["runtime"] == "agents_sdk"
    assert data["release_status"] == "BLOCKED"
    assert data["approval"]["allowed"] is False
    assert data["security"]["destructive_actions"] == "disabled"
    assert data["agent_runtime_summary"] == "live manager summary"
