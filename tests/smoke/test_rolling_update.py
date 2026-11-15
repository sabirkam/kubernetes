"""Rolls the backend between v1 and v2 (both images must be loaded, see `make update`) while polling the frontend."""

import subprocess
import time

import httpx

from conftest import kubectl


def test_rolling_update_has_no_downtime(frontend):
    current = kubectl("get", "deployment/backend", "-o", "jsonpath={.spec.template.spec.containers[0].image}")
    target = "v1" if current.endswith(":v2") else "v2"

    kubectl("set", "image", "deployment/backend", f"backend=demo-backend:{target}")
    rollout = subprocess.Popen(["kubectl", "rollout", "status", "deployment/backend", "--timeout=180s"],
                               stdout=subprocess.DEVNULL)

    versions, errors = set(), []
    while rollout.poll() is None:
        try:
            versions.add(frontend.get("/").raise_for_status().json()["backend"]["version"])
        except httpx.HTTPError as exc:
            errors.append(repr(exc))
        time.sleep(0.2)

    assert rollout.returncode == 0, "rollout did not finish"
    assert not errors, f"{len(errors)} failed requests during rollout: {errors[:3]}"
    assert versions == {"v1", "v2"}, "old and new versions should be served side by side"
