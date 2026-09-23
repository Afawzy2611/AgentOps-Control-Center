from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "launch-desk"


def test_launch_stream_rejects_invalid_brief():
    response = client.post("/api/launch/stream", json={"product_brief": "x"})
    assert response.status_code == 422


def test_health_stays_public_with_api_key(monkeypatch):
    monkeypatch.setenv("AGENTOPS_API_KEY", "desk-key")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["api_key_configured"] is True


def test_launch_stream_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("AGENTOPS_API_KEY", "desk-key")
    monkeypatch.setenv("HOST", "0.0.0.0")
    payload = {
        "product_brief": "Launch a new analytics dashboard for engineering teams with a clear onboarding flow.",
        "audience": "Engineering teams",
        "launch_date": "2026-10-15",
        "constraints": "Small launch team",
        "available_assets": "Demo video",
    }
    denied = client.post("/api/launch/stream", json=payload)
    assert denied.status_code == 401

    from backend.auth import authorize_headers
    ok, err = authorize_headers({"Authorization": "Bearer desk-key"}, bind_host="0.0.0.0")
    assert ok is True and err is None
    bad, _ = authorize_headers({"Authorization": "Bearer wrong"}, bind_host="0.0.0.0")
    assert bad is False
