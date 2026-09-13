import os
from typing import Any

from agents import Agent, RunConfig

from .models import LaunchBrief, LaunchPlan
from .tools import (
    check_launch_readiness,
    draft_channel_copy,
    extract_launch_tasks,
    generate_owner_checklist,
)

MODEL = os.getenv("LAUNCH_DESK_MODEL", "gpt-6-astra")

INSTRUCTIONS = """
You are Launch Desk, an engineering launch-planning agent.

Goal: turn a rough launch brief into an actionable release plan that an engineering team can execute.

Success criteria:
- Use the deterministic tools to ground the plan.
- Always call check_launch_readiness and extract_launch_tasks.
- Call generate_owner_checklist and draft_channel_copy before finalizing.
- Prioritize tasks by launch risk and dependency, not by arbitrary ordering.
- Separate known facts from assumptions.
- Never invent product capabilities, metrics, customers, dates, assets, owners, or commitments that were not provided.
- If a material input is missing, put a focused question in follow_up_questions rather than guessing.
- Return a complete LaunchPlan with an executive summary, prioritized plan, risks, owner checklist, channel copy, follow-up questions, and readiness score.

Keep recommendations practical. A launch plan should make the next actions obvious.
""".strip()


def build_agent() -> Agent[Any]:
    return Agent(
        name="Launch Desk",
        model=MODEL,
        instructions=INSTRUCTIONS,
        tools=[
            extract_launch_tasks,
            check_launch_readiness,
            generate_owner_checklist,
            draft_channel_copy,
        ],
        output_type=LaunchPlan,
    )


def run_config(group_id: str | None = None) -> RunConfig:
    return RunConfig(
        model=MODEL,
        workflow_name="Launch Desk",
        group_id=group_id,
        trace_include_sensitive_data=False,
        trace_metadata={"product": "launch-desk"},
    )


def brief_to_input(brief: LaunchBrief) -> str:
    return (
        "Create the launch plan for this brief.\n\n"
        f"Product brief:\n{brief.product_brief}\n\n"
        f"Audience:\n{brief.audience}\n\n"
        f"Launch date:\n{brief.launch_date}\n\n"
        f"Constraints:\n{brief.constraints or 'Not provided'}\n\n"
        f"Available assets:\n{brief.available_assets or 'Not provided'}"
    )
