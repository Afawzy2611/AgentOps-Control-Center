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

The primary hosted deployment is Railway. The repository includes `railway.toml` with the explicit start command and `/api/health` deployment healthcheck. `render.yaml` remains as a secondary hosting fallback.

Keep `AGENT_RUNTIME=deterministic` for the initial hosted baseline. Switch to `agents_sdk` only after the live SDK path has been validated and `OPENAI_API_KEY` is configured as a secret in the hosting environment.

## Development skills

The repository tracks `mattpocock/skills` as a development-only Git submodule under `vendor/mattpocock-skills`. It is not trusted as a runtime policy source.

## Live AI phase
This build intentionally does **not** call an external model and does not require an API key. The project includes an isolated OpenAI Agents SDK runtime that adds manager/specialist orchestration while preserving the deterministic policy engine and human approval boundary. OpenAI's current Agents SDK supports these primitives and multi-agent orchestration. See the official documentation.

Before enabling live model calls, credentials and production action permissions must be explicitly configured.

## Agents SDK runtime

The project includes an isolated OpenAI Agents SDK runtime behind `AGENT_RUNTIME`. The deterministic runtime remains the reference implementation and rollback path. Set `AGENT_RUNTIME=agents_sdk` only after installing `openai-agents` and configuring `OPENAI_API_KEY`. `POST /api/run` selects the configured runtime; `POST /api/run-demo` remains deterministic.
