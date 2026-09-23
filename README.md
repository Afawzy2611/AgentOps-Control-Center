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
- Optional external evidence layer with an Airbyte Agent SDK adapter
- Default-deny external connector authorization, bounded retries/output, provenance and audit metadata
- Deferred external evidence tools for the OpenAI Agents SDK

## Run
```bash
./run_demo.sh
```
Open `http://127.0.0.1:8787`.


## Authentication

Mutating and data-export routes (`/api/state`, `/api/export`, `/api/run`, `/api/run-demo`, `/api/decision`, and Launch Desk `/api/launch/stream`) require a shared API key when auth is enabled. `/api/health` stays public.

| Env var | Purpose |
|---|---|
| `AGENTOPS_API_KEY` | Shared secret accepted via `Authorization: Bearer …` or `X-API-Key` |
| `REQUIRE_AUTH` | Set to `1`/`true` to fail closed even on loopback when no key is configured |
| `HOST` | Non-loopback binds (`0.0.0.0`, etc.) fail closed if `AGENTOPS_API_KEY` is unset |

Local demo on `127.0.0.1`/`localhost` without a key logs a warning and allows unauthenticated access. Public or flagged deployments return `401` until a key is set. The control-center UI reads an optional key from `localStorage.AGENTOPS_API_KEY` (or `window.AGENTOPS_API_KEY`).

Per-run state: `/api/run` and `/api/run-demo` return a `run_id`. `/api/state`, `/api/export`, and `/api/decision` require that `run_id` (query or JSON) and only act on that run.

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

## External evidence / Airbyte

The external evidence layer is optional and does not change the deterministic release gate. The Airbyte adapter imports the Airbyte Agent SDK lazily, exposes only the progressive read-oriented operations (`inspect_connector`, `read_skill_docs`, and `execute`), rejects non-read connector actions, bounds returned text, retries only transient provider failures, and emits provenance/audit metadata without recording secrets.

Install the optional provider dependency only when using the adapter:

```bash
pip install airbyte-agent-sdk
```

Configure an explicit `EvidencePolicy` allowlist before constructing `AirbyteEvidenceProvider`. Do not place connector credentials or tokens in source control or audit records. Airbyte's current Agent SDK supports OpenAI Agents integration and its recommended connector flow is inspect → read skill docs → execute.

## Agents SDK runtime

The project includes an isolated OpenAI Agents SDK runtime behind `AGENT_RUNTIME`. The deterministic runtime remains the reference implementation and rollback path. Set `AGENT_RUNTIME=agents_sdk` only after installing `openai-agents` and configuring `OPENAI_API_KEY`. `POST /api/run` selects the configured runtime; `POST /api/run-demo` remains deterministic.
