import httpx
import pytest
from fastapi.testclient import TestClient

from app import app, get_client

BACKEND_REPLY = {"service": "backend", "version": "v1", "pod": "backend-1", "node": "demo-worker2"}


@pytest.fixture
def client_with_backend():
    """Returns a factory: TestClient whose backend calls are answered by `handler`."""

    def make(handler) -> TestClient:
        async def mocked_client():
            async with httpx.AsyncClient(base_url="http://backend", transport=httpx.MockTransport(handler)) as c:
                yield c

        app.dependency_overrides[get_client] = mocked_client
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def test_index_combines_frontend_and_backend_data(client_with_backend, monkeypatch):
    monkeypatch.setenv("POD_NAME", "frontend-1")
    client = client_with_backend(lambda request: httpx.Response(200, json=BACKEND_REPLY))

    body = client.get("/").json()

    assert body["service"] == "frontend"
    assert body["pod"] == "frontend-1"
    assert body["backend"] == BACKEND_REPLY


def test_backend_unreachable_returns_503(client_with_backend):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    response = client_with_backend(refuse).get("/")

    assert response.status_code == 503
    assert "backend unavailable" in response.json()["detail"]


def test_backend_error_status_returns_503(client_with_backend):
    response = client_with_backend(lambda request: httpx.Response(500)).get("/")

    assert response.status_code == 503
