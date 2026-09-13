import json
import re
from datetime import datetime

from agents import function_tool


@function_tool
def extract_launch_tasks(product_brief: str, audience: str, launch_date: str, constraints: str) -> str:
    """Extract a practical task backlog from the supplied launch brief without external side effects."""
    brief = product_brief.strip()
    constraints_text = constraints.strip() or "No explicit constraints supplied."
    phrases = [p.strip() for p in re.split(r"[.!?\n]+", brief) if p.strip()]
    task_seed = phrases[:4] or ["Clarify launch scope and success criteria"]
    tasks = []
    for index, phrase in enumerate(task_seed, start=1):
        tasks.append(
            {
                "title": f"Validate launch requirement: {phrase[:80]}",
                "priority": "P0" if index == 1 else "P1",
                "owner": "Product",
                "due": launch_date,
                "rationale": f"This item is directly implied by the launch brief for {audience}.",
            }
        )
    tasks.extend(
        [
            {"title": "Confirm launch readiness evidence", "priority": "P0", "owner": "Engineering", "due": launch_date, "rationale": "A launch should not rely on unverified assumptions."},
            {"title": "Finalize channel copy and asset mapping", "priority": "P1", "owner": "Marketing", "due": launch_date, "rationale": "Audience-facing material needs an owner and final review."},
            {"title": "Run launch-day monitoring and rollback check", "priority": "P1", "owner": "Operations", "due": launch_date, "rationale": "Operational readiness reduces launch-day recovery time."},
        ]
    )
    return json.dumps({"tasks": tasks, "constraints_observed": constraints_text}, ensure_ascii=False)


@function_tool
def check_launch_readiness(product_brief: str, audience: str, launch_date: str, constraints: str, available_assets: str) -> str:
    """Score launch readiness against a small deterministic rubric."""
    checks = {
        "brief_defined": len(product_brief.strip()) >= 40,
        "audience_defined": len(audience.strip()) >= 5,
        "date_defined": bool(launch_date.strip()),
        "constraints_defined": bool(constraints.strip()),
        "assets_defined": bool(available_assets.strip()),
    }
    score = round(sum(checks.values()) / len(checks) * 100)
    gaps = [name for name, passed in checks.items() if not passed]
    return json.dumps({"score": score, "checks": checks, "gaps": gaps}, ensure_ascii=False)


@function_tool
def generate_owner_checklist(audience: str, launch_date: str, available_assets: str) -> str:
    """Generate a side-effect-free ownership checklist for the launch."""
    assets = available_assets.strip() or "No assets listed"
    checklist = [
        f"Product owner: confirm scope, audience, and launch success criteria for {audience}.",
        f"Engineering owner: confirm production readiness and rollback path before {launch_date}.",
        "QA owner: complete critical-path regression and document open defects.",
        "Marketing owner: approve launch copy and map each message to an available asset.",
        "Operations owner: confirm monitoring, escalation contacts, and launch-day coverage.",
        f"Asset check: reconcile the launch against the supplied asset list: {assets}.",
    ]
    return json.dumps({"checklist": checklist}, ensure_ascii=False)


@function_tool
def draft_channel_copy(product_brief: str, audience: str, launch_date: str) -> str:
    """Draft concise channel-specific launch copy using only the supplied facts."""
    summary = product_brief.strip().replace("\n", " ")[:240]
    copy = {
        "email": f"Subject: A new launch for {audience}\n\nWe’re preparing to launch: {summary}. Launch date: {launch_date}.",
        "linkedin": f"We’re getting ready to launch a new product update for {audience}: {summary}. Target launch: {launch_date}.",
        "in_app": f"Coming {launch_date}: {summary}",
    }
    return json.dumps(copy, ensure_ascii=False)
