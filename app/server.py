import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .agentops import build_run_from_sdk_report, run_demo
from .auth import authorize_request, get_configured_api_key, require_auth_enabled, warn_if_auth_disabled
from .runtime import get_runtime

ROOT = Path(__file__).parent
INDEX = ROOT / "static" / "index.html"

_RUNS_LOCK = threading.Lock()
_RUNS: dict[str, dict] = {}
_MAX_RUNS = 100

# Public routes that never require an API key.
PUBLIC_PATHS = frozenset({"/", "/api/health"})
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def _store_run(run: dict) -> dict:
    with _RUNS_LOCK:
        _RUNS[run["run_id"]] = run
        while len(_RUNS) > _MAX_RUNS:
            oldest = next(iter(_RUNS))
            _RUNS.pop(oldest, None)
    return run


def _get_run(run_id: str | None) -> dict | None:
    if not run_id:
        return None
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


def _run_count() -> int:
    with _RUNS_LOCK:
        return len(_RUNS)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _json_error(self, status: int, message: str):
        self._send(status, json.dumps({"error": message}))

    def _check_auth(self, path: str) -> bool:
        # Deny-by-default for /api/* except the explicit public allow-list.
        if path in PUBLIC_PATHS:
            return True
        if path.startswith("/api/"):
            ok, err = authorize_request(self.headers, bind_host=os.getenv("HOST", "0.0.0.0"))
            if ok:
                return True
            self._json_error(401, err or "unauthorized")
            return False
        return True

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._check_auth(path):
            return
        if path == "/":
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/health":
            runtime = get_runtime()
            bind_host = os.getenv("HOST", "0.0.0.0")
            payload = {
                "status": "ok",
                "mode": "safe-demo",
                "runtime": runtime.name,
                "runtime_available": runtime.available,
                "run_count": _run_count(),
                "external_actions_enabled": False,
            }
            # Strip detailed auth posture from public health on non-loopback binds.
            if bind_host.strip().lower() in _LOOPBACK:
                payload["auth_required"] = require_auth_enabled(bind_host=bind_host)
                payload["api_key_configured"] = get_configured_api_key() is not None
            self._send(200, json.dumps(payload))
        elif path == "/api/state":
            qs = parse_qs(parsed.query)
            run_id = (qs.get("run_id") or [None])[0]
            run = _get_run(run_id)
            if run_id and run is None:
                self._json_error(404, "unknown run_id")
                return
            self._send(200, json.dumps(run or {"status": "idle"}))
        elif path == "/api/export":
            qs = parse_qs(parsed.query)
            run_id = (qs.get("run_id") or [None])[0]
            if not run_id:
                self._json_error(400, "run_id query parameter is required")
                return
            run = _get_run(run_id)
            if run is None:
                self._json_error(404, "unknown run_id")
                return
            self._send(200, json.dumps(run, indent=2), "application/json; charset=utf-8")
        else:
            self._json_error(404, "not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._check_auth(path):
            return
        if path in {"/api/run-demo", "/api/run"}:
            payload = self._read_json()
            project = payload.get("project") or "AgentOps Final Demo"
            runtime = get_runtime() if path == "/api/run" else type(
                "Runtime", (), {"name": "deterministic", "available": True}
            )()
            if not runtime.available:
                self._send(503, json.dumps({
                    "error": "selected agent runtime is unavailable",
                    "runtime": runtime.name,
                }))
                return
            if runtime.name == "agents_sdk":
                try:
                    from .agents_runtime import run_manager
                    report = run_manager(project)
                except Exception as exc:
                    self._send(502, json.dumps({
                        "error": "agents runtime failed",
                        "detail": str(exc),
                    }))
                    return
                run = build_run_from_sdk_report(project, report)
                run["security"]["external_actions_enabled"] = False
                run["security"]["destructive_actions"] = "disabled"
            else:
                run = run_demo(project, runtime="deterministic")
            run["security"]["api_key_configured"] = get_configured_api_key() is not None
            _store_run(run)
            self._send(200, json.dumps(run))
            return
        if path == "/api/decision":
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._json_error(400, "invalid JSON")
                return
            if not isinstance(payload, dict):
                self._json_error(400, "invalid JSON")
                return
            decision = payload.get("decision")
            run_id = payload.get("run_id")
            if decision not in {"APPROVE", "REJECT", "REQUEST_CHANGES"}:
                self._json_error(400, "invalid decision")
                return
            if not run_id:
                self._json_error(400, "run_id is required")
                return
            run = _get_run(run_id)
            if run is None:
                self._send(409, json.dumps({
                    "error": "run analysis before making a decision",
                    "run_id": run_id,
                }))
                return
            if decision == "APPROVE" and not run["approval"]["allowed"]:
                self._send(409, json.dumps({
                    "decision": decision,
                    "executed": False,
                    "run_id": run_id,
                    "message": "Approval blocked: resolve CRITICAL/HIGH findings before production approval.",
                }))
                return
            run["approval"]["decision"] = decision
            _store_run(run)
            self._send(200, json.dumps({
                "decision": decision,
                "executed": False,
                "run_id": run_id,
                "message": "Decision recorded. Safe demo mode executed no external action.",
            }))
            return
        self._json_error(404, "not found")

    def log_message(self, fmt, *args):
        print(fmt % args)


def get_server_config():
    return os.getenv("HOST", "0.0.0.0"), int(os.getenv("PORT", "8787"))


def main():
    host, port = get_server_config()
    warn_if_auth_disabled()
    if require_auth_enabled(bind_host=host) and not get_configured_api_key():
        print(
            "WARNING: Auth is required (REQUIRE_AUTH or non-loopback HOST) but "
            "AGENTOPS_API_KEY is unset — non-health API routes will return 401."
        )
    elif get_configured_api_key():
        print("API key auth enabled for mutating and export routes.")
    print(f"AgentOps running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
