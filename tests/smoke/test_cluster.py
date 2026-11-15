import pytest

from conftest import kubectl_json, nodes_of


def test_cluster_has_at_least_two_ready_nodes():
    nodes = kubectl_json("get", "nodes")["items"]
    ready = [n for n in nodes if any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"])]

    assert len(ready) >= 2


@pytest.mark.parametrize("app", ["backend", "frontend"])
def test_pods_run_on_multiple_nodes(app):
    assert len(nodes_of(app)) >= 2


def test_frontend_returns_data_from_backend(frontend):
    body = frontend.get("/").raise_for_status().json()

    assert body["service"] == "frontend"
    assert body["backend"]["service"] == "backend"
    assert body["backend"]["version"]


def test_requests_are_balanced_across_backend_pods(frontend):
    backend_pods = {frontend.get("/").json()["backend"]["pod"] for _ in range(20)}

    assert len(backend_pods) >= 2
