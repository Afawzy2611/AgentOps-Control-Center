import json

from backend.tools import (
    check_launch_readiness,
    draft_channel_copy,
    extract_launch_tasks,
    generate_owner_checklist,
)


def test_readiness_rubric_identifies_missing_inputs():
    raw = check_launch_readiness.on_invoke_tool(None, {"product_brief": "Short", "audience": "", "launch_date": "", "constraints": "", "available_assets": ""})
    data = json.loads(raw)
    assert data["score"] < 100
    assert "audience_defined" in data["gaps"]


def test_extract_tasks_is_deterministic_and_prioritized():
    raw = extract_launch_tasks.on_invoke_tool(None, {"product_brief": "Launch the dashboard. Improve onboarding.", "audience": "Engineering", "launch_date": "2026-10-15", "constraints": "One week"})
    data = json.loads(raw)
    assert data["tasks"][0]["priority"] == "P0"
    assert data["tasks"][-1]["owner"] == "Operations"


def test_owner_checklist_contains_all_core_owners():
    raw = generate_owner_checklist.on_invoke_tool(None, {"audience": "Teams", "launch_date": "2026-10-15", "available_assets": "Demo"})
    checklist = json.loads(raw)["checklist"]
    joined = " ".join(checklist)
    for owner in ("Product", "Engineering", "QA", "Marketing", "Operations"):
        assert owner in joined


def test_channel_copy_uses_supplied_facts_only():
    raw = draft_channel_copy.on_invoke_tool(None, {"product_brief": "New analytics dashboard", "audience": "Engineering teams", "launch_date": "2026-10-15"})
    data = json.loads(raw)
    assert "2026-10-15" in data["email"]
    assert "New analytics dashboard" in data["linkedin"]
