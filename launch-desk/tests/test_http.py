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
