import os
import subprocess
import sys
import time

import httpx
import pytest


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires live OpenAI API key")
def test_real_stream_emits_tool_and_text_events():
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8891"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            try:
                if httpx.get("http://127.0.0.1:8891/api/health", timeout=0.5).status_code == 200:
                    break
            except Exception:
                time.sleep(0.25)
        else:
            pytest.fail("Launch Desk server did not become ready")

        payload = {
            "product_brief": "Launch a new analytics dashboard for engineering teams with a clear onboarding flow and measurable adoption goals.",
            "audience": "Engineering teams",
            "launch_date": "2026-10-15",
            "constraints": "Small launch team; no destructive production changes during launch day.",
            "available_assets": "Demo video, landing page, onboarding guide",
        }
        saw_tool = False
        saw_delta = False
        with httpx.stream("POST", "http://127.0.0.1:8891/api/launch/stream", json=payload, timeout=180) as response:
            assert response.status_code == 200
            event = None
            for line in response.iter_lines():
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event:
                    if event == "tool_progress":
                        saw_tool = True
                    elif event == "text_delta":
                        saw_delta = True
                    if saw_tool and saw_delta:
                        break
        assert saw_tool, "expected at least one tool_progress event"
        assert saw_delta, "expected at least one text_delta event"
    finally:
        process.terminate()
        process.wait(timeout=10)
