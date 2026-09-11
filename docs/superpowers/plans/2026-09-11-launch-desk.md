# Launch Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a polished Launch Desk web app that uses the current OpenAI Agents SDK to transform a launch brief into a prioritized release plan with deterministic tools, streamed progress, and tracing.

**Architecture:** A FastAPI server owns the HTTP/SSE boundary and invokes one Launch Desk Agent. Four deterministic function tools provide task extraction, readiness scoring, owner checklist generation, and channel-copy drafting. A lightweight responsive frontend consumes the SSE stream and renders both progress and the final structured plan.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, OpenAI Agents SDK, Pydantic, vanilla HTML/CSS/JS, pytest, httpx.

**Spec:** `docs/launch-desk-migration-plan.md`

## Global Constraints

- Existing AgentOps Control Center code on `main` remains unchanged by the migration assessment.
- Launch Desk tools are deterministic and side-effect free.
- The agent must always call readiness and task-extraction tools before finalizing.
- Tracing must be enabled with sensitive data capture disabled for Launch Desk runs.
- Real end-to-end verification must use a configured `OPENAI_API_KEY` and consume the local SSE endpoint to completion.
- Do not use the deprecated Assistants API or legacy Chat Completions scaffolding.

---

### Task 1: Agent data contract and deterministic tools

**Files:**
- Create: `launch-desk/backend/models.py`
- Create: `launch-desk/backend/tools.py`
- Test: `launch-desk/tests/test_tools.py`

**Interfaces:**
- `LaunchBrief` validates `product_brief`, `audience`, `launch_date`, `constraints`, and `available_assets`.
- `extract_launch_tasks(...)` returns JSON with prioritized tasks.
- `check_launch_readiness(...)` returns JSON with score, checks, and gaps.
- `generate_owner_checklist(...)` returns JSON with owner checklist items.
- `draft_channel_copy(...)` returns JSON keyed by channel.

- [x] Write deterministic tool tests.
- [x] Implement the Pydantic contract.
- [x] Implement the four side-effect-free tools.
- [ ] Run `pytest launch-desk/tests/test_tools.py -q` in a real Python environment and fix any SDK tool-wrapper compatibility issue found.

### Task 2: Agents SDK orchestration

**Files:**
- Create: `launch-desk/backend/agent.py`

**Interfaces:**
- `build_agent()` returns the Launch Desk `Agent`.
- `run_config(group_id)` returns an SDK `RunConfig` with tracing and privacy settings.
- `brief_to_input(brief)` converts the validated brief to model input.

- [x] Define outcome-first agent instructions.
- [x] Register all four tools.
- [x] Require readiness and task extraction tool calls.
- [x] Configure model through `LAUNCH_DESK_MODEL` with `gpt-5.6-terra` as the default.
- [x] Disable sensitive trace payload capture.
- [ ] Run a non-streaming SDK smoke test with a configured API key.

### Task 3: Streaming API

**Files:**
- Create: `launch-desk/backend/main.py`
- Create: `launch-desk/backend/__init__.py`
- Test: `launch-desk/tests/test_http.py`
- Test: `launch-desk/tests/test_stream_contract.py`

**Interfaces:**
- `GET /api/health` returns service health.
- `POST /api/launch/stream` accepts `LaunchBrief` JSON and emits SSE events: `status`, `tool_progress`, `text_delta`, `complete`, and `error`.

- [x] Implement the FastAPI route.
- [x] Consume `Runner.run_streamed()` until the iterator completes.
- [x] Emit a progress event for tool calls.
- [x] Emit model text deltas from raw Responses events.
- [x] Surface `run_loop_exception` after stream consumption.
- [x] Add HTTP validation tests.
- [x] Add the live-stream contract test gated on `OPENAI_API_KEY`.

### Task 4: Frontend

**Files:**
- Create: `launch-desk/frontend/index.html`
- Create: `launch-desk/frontend/app.js`
- Create: `launch-desk/frontend/styles.css`

**Interfaces:**
- Form fields map one-to-one to `LaunchBrief`.
- Browser consumes `/api/launch/stream` and renders tool progress, streamed model text, readiness score, plan, risks, checklist, copy, and questions.

- [x] Build responsive launch brief form.
- [x] Add progressive status and tool-event UI.
- [x] Add structured final result rendering.
- [x] Add responsive mobile layout.
- [ ] Verify the rendered page and accessibility basics in a browser.

### Task 5: Setup and validation

**Files:**
- Create: `launch-desk/README.md`
- Create: `launch-desk/requirements.txt`
- Create: `launch-desk/.env.example`

- [x] Document environment setup and `OPENAI_API_KEY`.
- [x] Document `LAUNCH_DESK_MODEL`.
- [x] Document local server commands.
- [x] Document unit and real end-to-end tests.
- [ ] Run the full unit suite.
- [ ] Start the local server.
- [ ] POST a real launch brief to `/api/launch/stream`.
- [ ] Confirm at least one `tool_progress` event and one `text_delta` event.
- [ ] Confirm a `complete` event and structured final result.

### Task 6: Migration assessment

**Files:**
- Create: `docs/launch-desk-migration-plan.md`

- [x] Map current Responses API usage.
- [x] Map prompts, tools, streaming, and state.
- [x] Decide migration boundary.
- [x] Define architecture, tests, setup, rollback, and validation checklist.

