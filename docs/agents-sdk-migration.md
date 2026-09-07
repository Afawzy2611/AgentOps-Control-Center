# AgentOps Agents SDK Migration

## Runtime model

AgentOps now supports two runtimes:

- `AGENT_RUNTIME=deterministic` — the original safe reference implementation.
- `AGENT_RUNTIME=agents_sdk` — the OpenAI Agents SDK manager runtime.

The deterministic runtime remains the release-policy reference and rollback path. The Agents SDK runtime currently adds the manager/specialist orchestration layer and records its consolidated summary in `agent_runtime_summary`; external/destructive actions remain disabled.

## Install

Install the project requirements, including `openai-agents`, then provide `OPENAI_API_KEY` before selecting the SDK runtime.

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
export AGENT_RUNTIME=agents_sdk
```

The current OpenAI Agents SDK uses the Responses API by default for OpenAI models and provides agents-as-tools, guardrails, MCP, sessions, human-in-the-loop and tracing. See the official documentation: https://openai.github.io/openai-agents-python/

## API

- `POST /api/run-demo` always executes the deterministic reference runtime.
- `POST /api/run` uses `AGENT_RUNTIME`.
- `GET /api/health` reports runtime selection and availability.

## Safety boundary

The SDK manager is not an authorization engine. Release gates and human approval remain application-controlled. Do not connect action-capable MCP/shell tools until their allowlists, approvals, and regression tests are in place.
