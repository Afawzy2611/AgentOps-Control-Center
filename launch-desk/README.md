# Launch Desk — Agents SDK app

Launch Desk turns a rough launch brief into an actionable release plan. It uses the current OpenAI Agents SDK with deterministic function tools, streamed progress, and built-in tracing.

## Project layout

```text
launch-desk/
  backend/
    main.py
    agent.py
    models.py
    tools.py
  frontend/
    index.html
    app.js
    styles.css
  tests/
    test_tools.py
    test_http.py
    test_stream_contract.py
  requirements.txt
  .env.example
  README.md
```

## Requirements

- Python 3.11+
- `OPENAI_API_KEY`
- An OpenAI API project with API access

## Setup

```bash
cd launch-desk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`. Never commit it.

Optional model selection:

```text
LAUNCH_DESK_MODEL=gpt-5.6-terra
```

For maximum planning quality, a deployment can use `gpt-6-astra`.

For privacy-conscious tracing, Launch Desk sets `trace_include_sensitive_data=False` in the agent run configuration.

## Run

```bash
uvicorn backend.main:app --reload --port 8890
```

Open `http://127.0.0.1:8890`.

The API endpoint is `POST /api/launch/stream` and returns `text/event-stream`.

## Test

```bash
pytest -q
```

The unit/contract suite does not require a live model key. The real end-to-end verification requires `OPENAI_API_KEY` and must call the local endpoint, consume the stream to completion, and observe both `tool_progress` and `text_delta` events.

## Agent behavior

The agent is instructed to:

1. Identify missing information.
2. Call the readiness rubric and task extraction tools.
3. Produce a prioritized launch plan.
4. Produce a risk register.
5. Produce an owner checklist.
6. Draft channel-specific launch copy.
7. Ask focused follow-up questions when material information is missing.

The tool layer is deliberately deterministic and side-effect free. This makes it easy to test and extend with additional tools or future specialist handoffs.

## Extending the agent

Add deterministic tools in `backend/tools.py`, register them in `backend/agent.py`, add unit tests, then add a streaming contract case if the tool should be visible in the UI.

Use handoffs only when a separate specialist has a distinct responsibility that cannot be expressed cleanly as a deterministic tool.
