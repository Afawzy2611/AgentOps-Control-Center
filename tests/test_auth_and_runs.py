"""Tests for API auth gate and per-run state isolation."""

import json
import threading
from http.client import HTTPConnection

import pytest

from app import server
from app.auth import authorize_request, extract_api_key, require_auth_enabled


@pytest.fixture
def clear_runs():
    with server._RUNS_LOCK:
        server._RUNS.clear()
    yield
    with server._RUNS_LOCK:
        server._RUNS.clear()


@pytest.fixture
def http_server(monkeypatch, clear_runs):
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.delenv("AGENTOPS_API_KEY", raising=False)
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    yield host, port
    httpd.shutdown()
    httpd.server_close()


def _request(host, port, method, path, body=None, headers=None):
    conn = HTTPConnection(host, port, timeout=5)
    payload = None if body is None else json.dumps(body).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    conn.request(method, path, body=payload, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    try:
        parsed = json.loads(data.decode() or "null")
    except json.JSONDecodeError:
        parsed = data.decode()
    return resp.status, parsed


def test_extract_api_key_bearer_and_header():
    assert extract_api_key({"Authorization": "Bearer secret-1"}) == "secret-1"
    assert extract_api_key({"X-API-Key": "secret-2"}) == "secret-2"
    assert extract_api_key({}) is None


def test_require_auth_fail_closed_on_public_bind(monkeypatch):
    monkeypatch.delenv("AGENTOPS_API_KEY", raising=False)
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    assert require_auth_enabled(bind_host="0.0.0.0") is True
    assert require_auth_enabled(bind_host="127.0.0.1") is False
    monkeypatch.setenv("REQUIRE_AUTH", "1")
    assert require_auth_enabled(bind_host="127.0.0.1") is True


def test_authorize_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setenv("AGENTOPS_API_KEY", "expected")
    ok, err = authorize_request({}, bind_host="127.0.0.1")
    assert ok is False
    assert "unauthorized" in (err or "")
    ok, _ = authorize_request({"Authorization": "Bearer expected"}, bind_host="127.0.0.1")
    assert ok is True


def test_health_remains_public(http_server, monkeypatch):
    monkeypatch.setenv("AGENTOPS_API_KEY", "test-key")
    host, port = http_server
    status, body = _request(host, port, "GET", "/api/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["api_key_configured"] is True


def test_protected_routes_require_key(http_server, monkeypatch):
    monkeypatch.setenv("AGENTOPS_API_KEY", "test-key")
    host, port = http_server
    status, body = _request(host, port, "POST", "/api/run-demo", {"project": "x"})
    assert status == 401
    assert "unauthorized" in body["error"]

    status, body = _request(
        host, port, "POST", "/api/run-demo", {"project": "x"},
        headers={"X-API-Key": "test-key"},
    )
    assert status == 200
    assert body["run_id"]
    run_id = body["run_id"]

    status, body = _request(host, port, "GET", f"/api/state?run_id={run_id}")
    assert status == 401

    status, body = _request(
        host, port, "GET", f"/api/state?run_id={run_id}",
        headers={"Authorization": "Bearer test-key"},
    )
    assert status == 200
    assert body["run_id"] == run_id


def test_per_run_state_isolation(http_server):
    host, port = http_server
    _, run_a = _request(host, port, "POST", "/api/run-demo", {"project": "A"})
    _, run_b = _request(host, port, "POST", "/api/run-demo", {"project": "B"})
    assert run_a["run_id"] != run_b["run_id"]

    status, state_a = _request(host, port, "GET", f"/api/state?run_id={run_a['run_id']}")
    assert status == 200
    assert state_a["project"] == "A"

    status, state_b = _request(host, port, "GET", f"/api/state?run_id={run_b['run_id']}")
    assert status == 200
    assert state_b["project"] == "B"

    status, _ = _request(host, port, "GET", "/api/export")
    assert status == 400

    status, exported = _request(host, port, "GET", f"/api/export?run_id={run_a['run_id']}")
    assert status == 200
    assert exported["run_id"] == run_a["run_id"]

    status, decision = _request(
        host, port, "POST", "/api/decision",
        {"decision": "REJECT", "run_id": run_a["run_id"]},
    )
    assert status == 200
    assert decision["run_id"] == run_a["run_id"]

    _, state_a2 = _request(host, port, "GET", f"/api/state?run_id={run_a['run_id']}")
    _, state_b2 = _request(host, port, "GET", f"/api/state?run_id={run_b['run_id']}")
    assert state_a2["approval"]["decision"] == "REJECT"
    assert state_b2["approval"]["decision"] == "PENDING"


def test_decision_requires_run_id(http_server):
    host, port = http_server
    status, body = _request(host, port, "POST", "/api/decision", {"decision": "REJECT"})
    assert status == 400
    assert "run_id" in body["error"]
