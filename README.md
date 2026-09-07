# AgentOps Control Center v2

A safe, deterministic demonstration of a production-oriented multi-agent engineering control plane.

## Included
- Master orchestration model with 8 agent roles
- Developer, Security, QA, Data, Research, Governance, Observability and Review agents
- Severity-based release gates (CRITICAL/HIGH block; MEDIUM conditional)
- Remediation queue with owners and finding IDs
- Human approval gate
- Structured audit timeline
- Security controls showing external/destructive actions disabled
- JSON export endpoint
- Responsive control-center UI
- TDD regression suite

## Run
```bash
./run_demo.sh
```
Open `http://127.0.0.1:8787`.

## Test
```bash
pytest -q
```

## Deployment

The repository includes `render.yaml` for a Render Free web-service deployment. Keep `AGENT_RUNTIME=deterministic` for the first deployment; switch to `agents_sdk` only after installing the SDK and configuring `OPENAI_API_KEY` as a Render secret.

## Development skills

The repository tracks `mattpocock/skills` as a development-only Git submodule under `vendor/mattpocock-skills`. It is not trusted as a runtime policy source.

## Live AI phase
This build intentionally does **not** call an external model and does not require an API key. The project now includes an isolated OpenAI Agents SDK runtime that adds manager/specialist orchestration while preserving the deterministic policy engine and human approval boundary. OpenAI's current Agents SDK supports these primitives and multi-agent orchestration. See the official docs: https://openai.github.io/openai-agents-python/ .

Before enabling live model calls, credentials and production action permissions must be explicitly configured.

## Agents SDK runtime

The project now includes an isolated OpenAI Agents SDK runtime behind `AGENT_RUNTIME`. The deterministic runtime remains the reference implementation and rollback path. Set `AGENT_RUNTIME=agents_sdk` only after installing `openai-agents` and configuring `OPENAI_API_KEY`. `POST /api/run` selects the configured runtime; `POST /api/run-demo` remains deterministic.
