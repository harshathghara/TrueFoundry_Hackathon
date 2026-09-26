"""HTTP bridge between the dashboard and TrueForge."""
import asyncio
import json
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.runner import SessionRunner

load_dotenv()

TRUEFORGE_BASE_URL = os.getenv("TRUEFORGE_BASE_URL", "http://localhost:8790")
MCP_PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", "http://localhost:8000/mcp")
AGENT_NAME = os.getenv("AGENT_NAME", "cloud-cost-janitor")
RUNNERS: dict[str, SessionRunner] = {}

app = FastAPI(title="Cloud Cost Janitor API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

_client = None


def get_client():
    global _client
    if _client is None:
        from trueforge_sdk import TrueForge
        _client = TrueForge(base_url=TRUEFORGE_BASE_URL, timeout=600)
    return _client


class ScanRequest(BaseModel):
    region: str = "us-east-1"


class Decision(BaseModel):
    tool_call_id: str
    thread_id: str
    allow: bool
    reason: str | None = None


class DecisionsRequest(BaseModel):
    decisions: list[Decision]


def _runner(session_id: str) -> SessionRunner:
    runner = RUNNERS.get(session_id)
    if runner is None:
        raise HTTPException(404, "unknown session")
    return runner


def scan_prompt(region: str) -> str:
    return (f"Run a cost cleanup for AWS region {region}. Follow your procedure: discover, price, "
            f"build the teardown plan in the sandbox, check blast radius, then request deletion of safe candidates.")


@app.post("/api/scan")
async def scan(req: ScanRequest):
    runner = SessionRunner(get_client(), AGENT_NAME, asyncio.get_running_loop())
    session_id = await run_in_threadpool(runner.start, scan_prompt(req.region))
    RUNNERS[session_id] = runner
    return {"session_id": session_id}


@app.get("/api/sessions/{session_id}/events")
async def events(session_id: str):
    runner = _runner(session_id)
    queue = runner.subscribe()

    async def gen():
        try:
            while True:
                event = await queue.get()
                yield {"data": json.dumps(event)}
        finally:
            runner.unsubscribe(queue)

    return EventSourceResponse(gen(), ping=15)


@app.post("/api/sessions/{session_id}/decisions")
async def decisions(session_id: str, req: DecisionsRequest):
    runner = _runner(session_id)
    await run_in_threadpool(runner.decide, [d.model_dump() for d in req.decisions])
    return {"ok": True}


@app.get("/api/sessions/{session_id}/audit")
async def audit(session_id: str):
    return {"audit": _runner(session_id).audit}


@app.get("/api/health")
async def health():
    async def up(url):
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                await c.get(url)
            return True
        except httpx.HTTPError:
            return False
    return {"trueforge": await up(f"{TRUEFORGE_BASE_URL}/api/v1/agents"), "mcp": await up(MCP_PUBLIC_URL)}
