"""OpenAI Agents SDK runtime for AgentOps.

The deterministic control-plane runtime remains authoritative for release policy.
This module owns only LLM-driven analysis/orchestration. It is intentionally
isolated so the application can fall back to the deterministic implementation.
"""

from typing import Any

AGENT_ROLES = [
    "Developer", "Security", "QA", "Data", "Research", "Governance", "Observability", "Review"
]

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
        from agents import Agent, Runner
    except ImportError as exc:
        raise RuntimeError(
            "Agents SDK runtime requested but openai-agents is not installed. "
            "Install the project requirements before selecting AGENT_RUNTIME=agents_sdk."
        ) from exc
    return Agent, Runner


def build_specialist_agents(model: str | None = None) -> dict[str, Any]:
    Agent, _ = _require_sdk()
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
        kwargs = {
            "name": name,
            "instructions": (
                f"You are the AgentOps {name} specialist. Your role is {role}. "
                f"Focus: {focus} Return only evidence-based findings. "
                "Do not approve releases or authorize actions. Keep severity to CRITICAL, HIGH, MEDIUM, or LOW. "
                "Return a score from 0 to 100."
            ),
            "output_type": AgentReport,
        }
        if model:
            kwargs["model"] = model
        agents[name] = Agent(**kwargs)
    return agents


def build_manager_agent(model: str | None = None) -> Any:
    Agent, _ = _require_sdk()
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

    tools = [
        specialist.as_tool(
            tool_name=f"review_{name.lower()}",
            tool_description=f"Run the {name} AgentOps specialist review and return its structured report.",
        )
        for name, specialist in specialists.items()
    ]
    kwargs = {
        "name": "AgentOps Manager",
        "instructions": (
            "Coordinate the AgentOps specialist reviews. You MUST call every specialist tool exactly once: "
            + ", ".join(f"review_{name.lower()}" for name in specialists)
            + ". Consolidate their structured reports into the reports array. "
            "Never approve a release, bypass policy, or authorize an external action. "
            "If a specialist fails, include a report for it with status FAILED and explain the failure."
        ),
        "tools": tools,
        "output_type": ManagerReport,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def run_manager(project: str, model: str | None = None) -> dict[str, Any]:
    """Run the SDK manager and return validated structured specialist evidence."""
    _, Runner = _require_sdk()
    manager = build_manager_agent(model=model)
    result = Runner.run_sync(
        manager,
        f"Review project '{project}' using the complete specialist fleet. Return the consolidated evidence and risks.",
    )
    final = result.final_output
    if hasattr(final, "model_dump"):
        return final.model_dump()
    if isinstance(final, dict):
        return final
    raise RuntimeError("Agents SDK manager returned an unexpected output type")
