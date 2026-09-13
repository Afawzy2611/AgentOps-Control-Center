"""OpenAI Agents SDK runtime for AgentOps with optional external evidence tools."""

from typing import Any, Iterable

AGENT_ROLES = ["Developer", "Security", "QA", "Data", "Research", "Governance", "Observability", "Review"]

SPECIALIST_SPECS = {
    "Developer": ("Implementation", "Review implementation architecture, boundaries, and maintainability."),
    "Security": ("Security & Threat Modeling", "Identify authorization, authentication, supply-chain, and tool security risks."),
    "QA": ("Verification & Regression", "Identify missing regression, contract, integration, and negative-path tests."),
    "Data": ("Analytics & Intelligence", "Review data quality, persistence, metrics, and analytical readiness."),
    "Research": ("Technical Research", "Evaluate architecture and relevant technical implementation choices."),
    "Governance": ("Policy & Compliance", "Review policy, approval, evidence, governance, and compliance requirements."),
    "Observability": ("Tracing & Monitoring", "Review auditability, telemetry, tracing, metrics, and operational monitoring."),
}


def _require_sdk():
    try:
        from agents import Agent, ModelSettings, Runner, ToolSearchTool, tool_namespace
    except ImportError as exc:
        raise RuntimeError("Agents SDK runtime requested but openai-agents is not installed. Install the project requirements before selecting AGENT_RUNTIME=agents_sdk.") from exc
    return Agent, Runner, ModelSettings, ToolSearchTool, tool_namespace


def build_specialist_agents(model: str | None = None) -> dict[str, Any]:
    Agent, _, _, _, _ = _require_sdk()
    from pydantic import BaseModel, Field

    class FindingModel(BaseModel):
        severity: str
        category: str
        title: str
        detail: str
        recommendation: str
        owner: str
        status: str = "OPEN"

    class AgentReport(BaseModel):
        agent: str
        role: str
        status: str
        summary: str
        findings: list[FindingModel] = Field(default_factory=list)
        score: int

    agents: dict[str, Any] = {}
    for name, (role, focus) in SPECIALIST_SPECS.items():
        kwargs = {"name": name, "instructions": f"You are the AgentOps {name} specialist. Your role is {role}. Focus: {focus} Return only evidence-based findings. Do not approve releases or authorize actions. Keep severity to CRITICAL, HIGH, MEDIUM, or LOW. Return a score from 0 to 100.", "output_type": AgentReport}
        if model:
            kwargs["model"] = model
        agents[name] = Agent(**kwargs)
    return agents


def build_external_evidence_tools(provider: Any, policy: Any, connectors: Iterable[str], max_output_chars: int = 100_000) -> list[Any]:
    """Build deferred, read-only OpenAI Agents tools backed by the evidence policy."""
    try:
        from agents import function_tool
    except ImportError as exc:
        raise RuntimeError("OpenAI Agents SDK is required for external evidence tools") from exc
    from .external_evidence import RetryPolicy, execute_evidence_operation

    tools = []
    for connector in connectors:
        connector_name = connector.replace("-", "_").replace(" ", "_").lower()

        def inspect(arguments: dict[str, Any] | None = None, _connector=connector):
            evidence, audit = execute_evidence_operation(provider, policy, _connector, "inspect_connector", arguments or {}, RetryPolicy(), max_output_chars)
            return {"evidence": evidence.__dict__, "audit": audit.__dict__}

        def read_skill_docs(arguments: dict[str, Any] | None = None, _connector=connector):
            evidence, audit = execute_evidence_operation(provider, policy, _connector, "read_skill_docs", arguments or {}, RetryPolicy(), max_output_chars)
            return {"evidence": evidence.__dict__, "audit": audit.__dict__}

        def execute_read(arguments: dict[str, Any] | None = None, _connector=connector):
            evidence, audit = execute_evidence_operation(provider, policy, _connector, "execute", arguments or {}, RetryPolicy(), max_output_chars)
            return {"evidence": evidence.__dict__, "audit": audit.__dict__}

        for suffix, function in (("inspect_connector", inspect), ("read_skill_docs", read_skill_docs), ("execute", execute_read)):
            tool = function_tool(function, name_override=f"external_{connector_name}_{suffix}", description_override=f"Read-only external evidence operation for the {connector} connector.", strict_mode=False, defer_loading=True)
            tools.append(tool)
    return tools


def build_manager_agent(model: str | None = None, external_provider: Any | None = None, external_policy: Any | None = None, external_connectors: Iterable[str] = ()) -> Any:
    Agent, _, ModelSettings, ToolSearchTool, tool_namespace = _require_sdk()
    from pydantic import BaseModel, Field

    specialists = build_specialist_agents(model=model)

    class FindingModel(BaseModel):
        severity: str
        category: str
        title: str
        detail: str
        recommendation: str
        owner: str
        status: str = "OPEN"

    class AgentReport(BaseModel):
        agent: str
        role: str
        status: str
        summary: str
        findings: list[FindingModel] = Field(default_factory=list)
        score: int

    class ManagerReport(BaseModel):
        summary: str
        reports: list[AgentReport] = Field(default_factory=list)

    specialist_tools = []
    for name, specialist in specialists.items():
        specialist_tool = specialist.as_tool(tool_name=f"review_{name.lower()}", tool_description=f"Run the {name} AgentOps specialist review and return its structured report.")
        specialist_tool.defer_loading = True
        specialist_tools.append(specialist_tool)

    specialist_tools = tool_namespace(name="agentops_specialists", description="AgentOps specialist review tools for implementation, security, QA, data, research, governance, and observability.", tools=specialist_tools)
    tools = [*specialist_tools]
    instructions = "Coordinate the AgentOps specialist reviews. First use tool search to load the agentops_specialists namespace. After loading it, you MUST call every specialist tool exactly once: " + ", ".join(f"review_{name.lower()}" for name in specialists) + ". Consolidate their structured reports into the reports array. Never approve a release, bypass policy, or authorize an external action. If a specialist fails, include a report for it with status FAILED and explain the failure."

    if external_provider is not None:
        if external_policy is None:
            raise ValueError("external_policy is required when external_provider is supplied")
        tools.extend(build_external_evidence_tools(external_provider, external_policy, external_connectors))
        instructions += " External evidence tools are supplemental and read-only; never treat external evidence as release authorization."

    kwargs = {"name": "AgentOps Manager", "instructions": instructions, "tools": [*tools, ToolSearchTool()], "model_settings": ModelSettings(tool_choice="auto"), "output_type": ManagerReport}
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def run_manager(project: str, model: str | None = None) -> dict[str, Any]:
    """Run the SDK manager and return validated structured specialist evidence."""
    _, Runner, _, _, _ = _require_sdk()
    manager = build_manager_agent(model=model)
    result = Runner.run_sync(manager, f"Review project '{project}' using the complete specialist fleet. Return the consolidated evidence and risks.")
    final = result.final_output
    if hasattr(final, "model_dump"):
        return final.model_dump()
    if isinstance(final, dict):
        return final
    raise RuntimeError("Agents SDK manager returned an unexpected output type")
