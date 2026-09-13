# Agents SDK Deferred Tool Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Responses-only deferred tool loading to the AgentOps manager while preserving the existing `Agent.as_tool()` specialist orchestration and deterministic release-policy gate.

**Architecture:** Keep the seven specialist agents as bounded `Agent.as_tool()` callables owned by the manager. Mark those generated tools for deferred loading, group them under one `agentops_specialists` namespace, and expose exactly one `ToolSearchTool()` so the Responses model loads the specialist surface on demand. The deterministic policy layer remains authoritative for release status, remediation, and approval.

**Tech Stack:** Python, OpenAI Agents SDK, Pydantic, pytest, GitHub Actions.

**Spec:** Existing AgentOps Agents SDK runtime plus OpenAI Agents SDK hosted tool-search guidance.

## Global Constraints

- Preserve the existing eight-role fleet and deterministic policy gate.
- Use `Agent.as_tool()` for specialist delegation; do not convert specialists to handoffs.
- Use Responses-only `ToolSearchTool()` and `tool_namespace()` for deferred loading.
- Keep model tool choice on `auto` for tool search compatibility.
- Do not enable destructive or external actions as part of this change.
- Do not require a live API key for unit tests.

---

### Task 1: Lock the deferred-tool contract with tests

**Files:**
- Modify: `tests/test_agentops.py`

**Interfaces:**
- `build_manager_agent(model: str | None) -> Agent` exposes seven deferred specialist tools plus one tool-search tool.

- [x] **Step 1: Write the failing test**

Add a test that supplies fake Agents SDK classes, builds the manager, and asserts there is exactly one `tool_search` tool, seven specialist tools, every specialist tool has `defer_loading=True`, and every specialist tool belongs to the `agentops_specialists` namespace.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest tests/test_agentops.py::test_manager_defers_specialist_agent_tools_and_adds_tool_search -v`

Expected: FAIL because the current manager exposes specialist tools immediately and has no `ToolSearchTool`.

- [ ] **Step 3: Implement the minimal runtime change**

Update `app/agents_runtime.py` to mark each `Agent.as_tool()` result as deferred, group the tools with `tool_namespace(name="agentops_specialists", ...)`, add exactly one `ToolSearchTool()`, and set manager `ModelSettings(tool_choice="auto")`.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `pytest tests/test_agentops.py::test_manager_defers_specialist_agent_tools_and_adds_tool_search -v`

Expected: PASS.

- [ ] **Step 5: Run the full regression suite**

Run: `pytest -q`

Expected: all existing deterministic/runtime tests and the new structural SDK test pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_agentops.py app/agents_runtime.py docs/superpowers/plans/2026-09-13-agents-sdk-tool-search.md
git commit -m "feat: defer AgentOps specialist tools"
```

---

### Verification Checklist

- [ ] Seven specialists still use `Agent.as_tool()`.
- [ ] Specialist tools are deferred rather than removed.
- [ ] Exactly one `ToolSearchTool()` is present.
- [ ] Specialist tools share the `agentops_specialists` namespace.
- [ ] Manager tool choice is `auto`.
- [ ] Deterministic release policy remains unchanged.
- [ ] No live API key is required by unit tests.
- [ ] Full pytest suite is green before the PR is created.
