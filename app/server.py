import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .agentops import run_demo, build_run_from_sdk_report
from .runtime import get_runtime

ROOT = Path(__file__).parent
INDEX = ROOT / "static" / "index.html"
LAST_RUN = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        global LAST_RUN
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/health":
            runtime = get_runtime()
            self._send(200, json.dumps({"status": "ok", "mode": "safe-demo", "runtime": runtime.name,
                                       "runtime_available": runtime.available, "run_available": LAST_RUN is not None,
                                       "external_actions_enabled": False}))
        elif path == "/api/state":
            self._send(200, json.dumps(LAST_RUN or {"status": "idle"}))
        elif path == "/api/export":
            self._send(200, json.dumps(LAST_RUN or {"status": "idle"}, indent=2), "application/json; charset=utf-8")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        global LAST_RUN
        path = urlparse(self.path).path
        if path in {"/api/run-demo", "/api/run"}:
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                payload = {}
            project = payload.get("project") or "AgentOps Final Demo"
            runtime = get_runtime() if path == "/api/run" else type("Runtime", (), {"name": "deterministic", "available": True})()
            if not runtime.available:
                self._send(503, json.dumps({"error": "selected agent runtime is unavailable", "runtime": runtime.name}))
                return
            if runtime.name == "agents_sdk":
                try:
                    from .agents_runtime import run_manager
                    report = run_manager(project)
                except Exception as exc:
                    self._send(502, json.dumps({"error": "agents runtime failed", "detail": str(exc)}))
                    return
                LAST_RUN = build_run_from_sdk_report(project, report)
                LAST_RUN["security"]["external_actions_enabled"] = False
                LAST_RUN["security"]["destructive_actions"] = "disabled"
            else:
                LAST_RUN = run_demo(project, runtime="deterministic")
            self._send(200, json.dumps(LAST_RUN))
            return
        if path == "/api/decision":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send(400, json.dumps({"error": "invalid JSON"})); return
            decision = payload.get("decision")
            if decision not in {"APPROVE", "REJECT", "REQUEST_CHANGES"}:
                self._send(400, json.dumps({"error": "invalid decision"})); return
            if LAST_RUN is None:
                self._send(409, json.dumps({"error": "run analysis before making a decision"})); return
            if decision == "APPROVE" and not LAST_RUN["approval"]["allowed"]:
                self._send(409, json.dumps({"decision": decision, "executed": False,
                    "message": "Approval blocked: resolve CRITICAL/HIGH findings before production approval."})); return
            LAST_RUN["approval"]["decision"] = decision
            self._send(200, json.dumps({"decision": decision, "executed": False,
                "message": "Decision recorded. Safe demo mode executed no external action."})); return
        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, fmt, *args):
        print(fmt % args)


def get_server_config():
    return os.getenv("HOST", "0.0.0.0"), int(os.getenv("PORT", "8787"))


def main():
    host, port = get_server_config()
    print(f"AgentOps running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
