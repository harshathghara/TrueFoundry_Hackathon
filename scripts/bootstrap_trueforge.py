"""Configure a local TrueForge server for Cloud Cost Janitor. Safe to re-run."""
import os
import sys

import httpx
from dotenv import load_dotenv

from agent.manifest import build_agent_manifest

MODEL_NAME = "janitor-model"
MODEL_FQN = f"openai/{MODEL_NAME}"
MCP_NAME = "aws-janitor"


def model_provider_body(api_key: str, model_id: str) -> dict:
    return {"manifest": {"type": "openai", "auth": {"api_key": api_key},
                         "models": [{"name": MODEL_NAME, "model_id": model_id, "properties": {}}]}}


def mcp_server_body(url: str) -> dict:
    return {"manifest": {"type": "remote", "name": MCP_NAME, "url": url,
                         "description": "AWS cost cleanup: discover idle resources, price them, check blast radius, delete with approval."}}


def sandbox_body(api_key: str) -> dict:
    # TrueForge v0.2.1 requires the interval/timeout fields; values = its shipped Daytona catalog defaults.
    return {"manifest": {"type": "daytona", "auth": {"api_key": api_key}, "exec_timeout_ms": 60000,
                         "auto_stop_interval_in_minutes": 5, "auto_archive_interval_in_minutes": 60,
                         "auto_delete_interval_in_minutes": 7200}}


def _check(resp: httpx.Response, what: str) -> httpx.Response:
    if resp.status_code >= 400:
        sys.exit(f"{what} failed: HTTP {resp.status_code} {resp.text}\nCompare with {resp.request.url.scheme}://{resp.request.url.host}:{resp.request.url.port}/api/v1/docs")
    print(f"ok  {what}")
    return resp


def bootstrap(base_url: str, env: dict, http: httpx.Client | None = None) -> None:
    http = http or httpx.Client(base_url=base_url, timeout=60)
    _check(http.put("/api/v1/settings/model-providers", json=model_provider_body(env["OPENAI_API_KEY"], env["OPENAI_MODEL_ID"])), "model provider")
    _check(http.put("/api/v1/settings/mcp-servers", json=mcp_server_body(env["MCP_PUBLIC_URL"])), "mcp server")
    _check(http.put("/api/v1/settings/sandbox-providers", json=sandbox_body(env["DAYTONA_API_KEY"])), "sandbox provider")

    name = env["AGENT_NAME"]
    manifest = build_agent_manifest(MODEL_FQN)
    existing = _check(http.get("/api/v1/agents", params={"agent_name": name}), "list agents").json()["data"]
    match = next((a for a in existing if a["name"] == name), None)
    description = "Finds idle AWS resources, prices them, and deletes only what a human approves."
    if match:
        _check(http.put(f"/api/v1/agents/{match['id']}", json={"description": description, "manifest": manifest}), "update agent")
    else:
        _check(http.post("/api/v1/agents", json={"name": name, "description": description, "manifest": manifest}), "create agent")


if __name__ == "__main__":
    load_dotenv()
    bootstrap(os.getenv("TRUEFORGE_BASE_URL", "http://localhost:8790"), dict(os.environ))
