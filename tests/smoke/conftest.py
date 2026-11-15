import json
import os
import subprocess

import httpx
import pytest

# 127.0.0.1, not localhost: on Windows localhost tries IPv6 first and the kind port mapping is IPv4-only (~2 s delay).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8080")


def kubectl(*args: str) -> str:
    return subprocess.run(["kubectl", *args], check=True, capture_output=True, text=True).stdout


def kubectl_json(*args: str) -> dict:
    return json.loads(kubectl(*args, "-o", "json"))


def nodes_of(app: str) -> set[str]:
    pods = kubectl_json("get", "pods", "-l", f"app={app}", "--field-selector", "status.phase=Running")["items"]
    return {pod["spec"]["nodeName"] for pod in pods}


@pytest.fixture
def frontend():
    # New connection per request, so calls are spread over frontend pods.
    with httpx.Client(base_url=FRONTEND_URL, timeout=3.0, limits=httpx.Limits(max_keepalive_connections=0)) as client:
        yield client
