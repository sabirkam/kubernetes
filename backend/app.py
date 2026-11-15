import os

from fastapi import FastAPI

app = FastAPI(title="backend")


@app.get("/")
def info() -> dict:
    return {
        "service": "backend",
        "version": os.getenv("APP_VERSION", "dev"),
        "pod": os.getenv("POD_NAME", "local"),
        "node": os.getenv("NODE_NAME", "local"),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
