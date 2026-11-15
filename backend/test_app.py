from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_info_reports_version_pod_and_node(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v9")
    monkeypatch.setenv("POD_NAME", "backend-abc")
    monkeypatch.setenv("NODE_NAME", "demo-worker")

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"service": "backend", "version": "v9", "pod": "backend-abc", "node": "demo-worker"}


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
