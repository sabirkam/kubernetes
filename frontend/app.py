import os
from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, FastAPI, HTTPException

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

app = FastAPI(title="frontend")


async def get_client() -> AsyncIterator[httpx.AsyncClient]:
    # No keep-alive: every call opens a new connection, so the Service balances it across backend pods.
    limits = httpx.Limits(max_keepalive_connections=0)
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=2.0, limits=limits) as client:
        yield client


@app.get("/")
async def index(client: httpx.AsyncClient = Depends(get_client)) -> dict:
    try:
        response = await client.get("/")
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"backend unavailable: {exc!r}") from exc
    return {
        "service": "frontend",
        "version": os.getenv("APP_VERSION", "dev"),
        "pod": os.getenv("POD_NAME", "local"),
        "node": os.getenv("NODE_NAME", "local"),
        "backend": response.json(),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
