# Responses API → Agents SDK Migration Assessment

## Scope
This assessment covers the existing `Afawzy2611/AgentOps-Control-Center` application on `main` and does not modify its existing code. The repository is not a direct Responses API application: the current runtime is a deterministic control-plane demo plus an isolated Agents SDK runtime.

## Current workflow map

### HTTP/API
- `GET /api/health` exposes runtime availability and whether a run exists.
- `GET /api/state` returns the last in-memory run.
- `GET /api/export` exports the last in-memory run.
- `POST /api/run` selects the configured runtime.
- `POST /api/run-demo` forces the deterministic reference runtime.
- `POST /api/decision` records APPROVE/REJECT/REQUEST_CHANGES while the deterministic release policy remains authoritative.

### Deterministic path
`app/server.py` calls `run_demo()` from `app/agentops.py`. This path owns release policy, findings, remediation state, approval behavior, and safe-mode constraints.

### Agents SDK path
`app/agents_runtime.py` defines specialist agents for Developer, Security, QA, Data, Research, Governance, and Observability. An AgentOps Manager uses specialist agents as tools and returns structured Pydantic reports. `Runner.run_sync()` currently executes the manager non-streaming.

### Responses API usage
A repository-wide code search for `client.responses`, `responses.create`, and `previous_response_id` returns no matches. The existing application therefore has no Responses API workflow to migrate.

### Prompts
The SDK prompts are embedded as agent instructions in `app/agents_runtime.py`. The deterministic runtime has its own fixed domain logic in `app/agentops.py`.

### Tools
The SDK runtime currently uses `Agent.as_tool()` for specialist delegation. There is no direct custom function-tool registry, MCP integration, or hosted tool flow in the current app.

### Streaming
No current application streaming workflow was found. `/api/run` returns one JSON response and the SDK path uses `Runner.run_sync()`.

### State
Application state is currently process-local through `LAST_RUN`. There is no Responses `previous_response_id`, SDK Session, durable conversation store, or resumable streamed state in the current app.

## Migration decision
A direct Responses API → Agents SDK migration is **not applicable** because the existing app is not built on the Responses API. The correct change is an incremental agentic enhancement, preserving the deterministic control plane.

### Keep outside the agent runtime
- HTTP/API boundary
- deterministic release policy
- human approval gate
- authorization/release gate
- durable business/audit state when introduced
- final authorization decisions

### Put inside Agents SDK
- specialist reasoning
- structured analysis
- tool orchestration
- optional handoffs
- streaming
- tracing
- session/resumable agent state
- evaluation harness

The SDK documentation explicitly positions the Agents SDK for workflows where the runtime should manage turns, tool execution, guardrails, handoffs, sessions, or resumable execution; the Responses API remains appropriate for lower-level workflows where the application owns the loop. The existing control center is best treated as a hybrid architecture rather than a full replacement. 

## Launch Desk architecture decision
The new Launch Desk app is an appropriate Agents SDK workload because it benefits from multiple deterministic tools, structured outputs, progressive streaming, tracing, and future specialist handoffs. It does not need autonomous side effects.

## Proposed architecture
```text
Frontend
  │ POST /api/launch/stream
  ▼
FastAPI streaming route
  │
  ▼
Launch Desk Agent
  ├── extract_launch_tasks
  ├── check_launch_readiness
  ├── generate_owner_checklist
  └── draft_channel_copy
  │
  ▼
Structured launch plan + streamed deltas
  │
  ├── tool progress events
  ├── model text deltas
  └── final result
```

The first version uses one orchestrator agent plus deterministic function tools. Handoffs are intentionally deferred until evals demonstrate a meaningful need for specialist agents. This follows the current SDK guidance to start with the smallest useful agentic architecture.

## State strategy
Launch Desk V1 is request-scoped and stateless at the server layer. A later iteration can add `SQLiteSession` or another durable SDK Session when multi-turn planning becomes a product requirement. The current brief itself is sufficient context for a single planning run.

## Streaming design
The server consumes `Runner.run_streamed()` and maps SDK events to application SSE events:
- `tool_progress` when a function tool executes
- `text_delta` for model text deltas
- `complete` with final output
- `error` for terminal failures

The stream is consumed to completion before the request ends, because the SDK documents that persistence, approvals, and other post-token work can finish after the final visible token.

## Tracing
Use SDK `RunConfig` with `workflow_name="Launch Desk"`, a request group ID, and `trace_include_sensitive_data=False` by default. This preserves observability without putting the submitted brief and tool payloads into trace data.

## Model
The current OpenAI model guidance lists GPT-6 Astra as the flagship model and GPT-5.6 Terra as the balanced intelligence/cost option. Launch Desk defaults to `gpt-5.6-terra` through `LAUNCH_DESK_MODEL`, while allowing a deployment to select `gpt-6-astra` when maximum planning quality is preferred.

## Tests to add
1. Tool unit tests for task extraction, readiness rubric, owner checklist, and copy drafting.
2. Agent contract test that requires the readiness tool and produces the expected sections.
3. Streaming adapter test proving `tool_progress`, `text_delta`, and `complete` events are emitted.
4. HTTP test for valid/invalid brief payloads.
5. End-to-end smoke test against a real local server using a configured `OPENAI_API_KEY`, consuming the SSE stream until both a tool event and model delta are observed.
6. Regression cases for missing launch date, missing audience, incomplete assets, and contradictory constraints.

## Setup documentation
Document Python/virtualenv setup, `OPENAI_API_KEY`, `LAUNCH_DESK_MODEL`, tracing privacy configuration, local server commands, frontend URL, tests, and the required real-API smoke test.

## Rollback
The existing AgentOps runtime is untouched on `main`. The Launch Desk work is isolated on a feature branch. If the SDK path fails, the branch can be abandoned without affecting the existing deterministic application. For Launch Desk itself, keep the tool layer deterministic and the agent endpoint replaceable so the API boundary can be temporarily switched to a deterministic fixture during development.

## Validation checklist
- [ ] Existing AgentOps code remains unchanged by this migration assessment.
- [ ] Launch Desk frontend loads.
- [ ] Brief form submits successfully.
- [ ] Backend emits SSE.
- [ ] At least one tool progress event is observed.
- [ ] At least one model text delta is observed.
- [ ] Final result includes prioritized plan, risks, owner checklist, copy suggestions, and follow-up questions.
- [ ] Missing critical inputs produce focused follow-up questions.
- [ ] Tool outputs are deterministic and unit-tested.
- [ ] SDK tracing is enabled with sensitive data capture disabled by default.
- [ ] Real API smoke test is executed before claiming end-to-end success.
