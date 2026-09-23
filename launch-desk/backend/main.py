import json
import os
import uuid
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from agents import Runner

from .agent import brief_to_input, build_agent, run_config
from .auth import authorize_headers, get_configured_api_key, require_auth_enabled, warn_if_auth_disabled
from .models import LaunchBrief

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    warn_if_auth_disabled()
    host = os.getenv("HOST", "127.0.0.1")
    if require_auth_enabled(bind_host=host) and not get_configured_api_key():
        print(
            "WARNING: Auth is required (REQUIRE_AUTH or non-loopback HOST) but "
            "AGENTOPS_API_KEY is unset — non-health API routes will return 401."
        )
    yield


app = FastAPI(title="Launch Desk", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


async def require_api_key(request: Request) -> None:
    ok, err = authorize_headers(request.headers, bind_host=os.getenv("HOST", "127.0.0.1"))
    if not ok:
        raise HTTPException(status_code=401, detail=err or "unauthorized")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    host = os.getenv("HOST", "127.0.0.1")
    return {
        "status": "ok",
        "service": "launch-desk",
        "auth_required": require_auth_enabled(bind_host=host),
        "api_key_configured": get_configured_api_key() is not None,
    }


def sse(event_type: str, payload: dict) -> bytes:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


@app.post("/api/launch/stream", dependencies=[Depends(require_api_key)])
async def launch_stream(brief: LaunchBrief) -> StreamingResponse:
    request_id = f"launch-{uuid.uuid4().hex[:12]}"

    async def generate():
        try:
            yield sse("status", {"request_id": request_id, "message": "Launch Desk is analyzing the brief."})
            agent = build_agent()
            result = Runner.run_streamed(
                agent,
                brief_to_input(brief),
                run_config=run_config(group_id=request_id),
                max_turns=8,
            )

            async for event in result.stream_events():
                if event.type == "run_item_stream_event":
                    if event.name == "tool_called":
                        raw_item = getattr(event.item, "raw_item", None)
                        name = getattr(raw_item, "name", None) or "tool"
                        yield sse("tool_progress", {"tool": name, "status": "started"})
                    elif event.name == "tool_output":
                        yield sse("tool_progress", {"tool": "tool", "status": "completed"})
                elif event.type == "raw_response_event":
                    data = event.data
                    if getattr(data, "type", "") == "response.output_text.delta":
                        delta = getattr(data, "delta", "")
                        if delta:
                            yield sse("text_delta", {"delta": delta})

            if result.run_loop_exception:
                raise result.run_loop_exception
            if not result.is_complete:
                raise RuntimeError("Launch Desk stream ended before the agent run completed.")

            final = result.final_output
            if hasattr(final, "model_dump"):
                final = final.model_dump()
            yield sse("complete", {"request_id": request_id, "result": final})
        except Exception as exc:
            yield sse("error", {"request_id": request_id, "error": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
