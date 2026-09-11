from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from agents import Runner

from .agent import brief_to_input, build_agent, run_config
from .models import LaunchBrief

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Launch Desk", version="1.0.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "launch-desk"}


def sse(event_type: str, payload: dict) -> bytes:
    import json
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


@app.post("/api/launch/stream")
async def launch_stream(brief: LaunchBrief) -> StreamingResponse:
    import uuid
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
                    item_type = getattr(event.item, "type", "")
                    if item_type == "tool_call_item":
                        raw_item = getattr(event.item, "raw_item", None)
                        name = getattr(raw_item, "name", "tool")
                        yield sse("tool_progress", {"tool": name, "status": "started"})
                    elif item_type == "tool_call_output_item":
                        yield sse("tool_progress", {"tool": "tool", "status": "completed"})
                elif event.type == "raw_response_event":
                    data = event.data
                    if getattr(data, "type", "") == "response.output_text.delta":
                        delta = getattr(data, "delta", "")
                        if delta:
                            yield sse("text_delta", {"delta": delta})
            if result.run_loop_exception:
                raise result.run_loop_exception
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
