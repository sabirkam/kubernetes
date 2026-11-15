"""Poll the frontend and print which backend version/pod answered. Stop with Ctrl+C."""

import time
from collections import Counter

import httpx

URL = "http://127.0.0.1:8080/"

seen = Counter()
# No keep-alive: every request opens a new connection, so it can land on a different frontend pod.
with httpx.Client(timeout=3.0, limits=httpx.Limits(max_keepalive_connections=0)) as client:
    try:
        while True:
            try:
                body = client.get(URL).raise_for_status().json()
                backend = body["backend"]
                seen[backend["version"]] += 1
                print(f"{body['pod']:<27} -> backend {backend['version']}  {backend['pod']:<27} @ {backend['node']}")
            except httpx.HTTPError as exc:
                seen["ERROR"] += 1
                print(f"ERROR {exc!r}")
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nsummary:", dict(seen))
