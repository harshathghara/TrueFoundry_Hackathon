import httpx
import pytest

from agent.manifest import build_agent_manifest
from scripts import bootstrap_trueforge as bt


def test_manifest_gates_every_destructive_tool():
    m = build_agent_manifest("openai/janitor-model")
    srv = m["mcp_servers"][0]
    assert srv["name"] == "aws-janitor"
    assert "@destructive" in srv["require_approval_for_tools"]
    for tool in ["delete_volume", "terminate_instance", "delete_load_balancer", "release_eip", "delete_snapshot"]:
        assert tool in srv["require_approval_for_tools"]
    assert m["config"]["sandbox"]["enabled"] is True
    assert m["config"]["ask_user_questions"]["enabled"] is False
    assert m["model"]["name"] == "openai/janitor-model"
    assert "Cloud Cost Janitor" in m["instructions"]


def test_bodies():
    assert bt.model_provider_body("sk", "gpt-5.2") == {"manifest": {
        "type": "openai", "auth": {"api_key": "sk"},
        "models": [{"name": "janitor-model", "model_id": "gpt-5.2", "properties": {}}]}}
    assert bt.mcp_server_body("http://localhost:8000/mcp")["manifest"]["type"] == "remote"
    assert bt.sandbox_body("dk") == {"manifest": {"type": "daytona", "auth": {"api_key": "dk"}, "exec_timeout_ms": 60000,
                                                  "auto_stop_interval_in_minutes": 5, "auto_archive_interval_in_minutes": 60,
                                                  "auto_delete_interval_in_minutes": 7200}}


def test_bootstrap_creates_agent_when_missing():
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path))
        if req.method == "GET" and req.url.path == "/api/v1/agents":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"data": {}})

    http = httpx.Client(base_url="http://tf", transport=httpx.MockTransport(handler))
    env = {"OPENAI_API_KEY": "sk", "OPENAI_MODEL_ID": "gpt-5.2", "DAYTONA_API_KEY": "dk",
           "MCP_PUBLIC_URL": "http://localhost:8000/mcp", "AGENT_NAME": "cloud-cost-janitor"}
    bt.bootstrap("http://tf", env, http)
    assert ("PUT", "/api/v1/settings/model-providers") in calls
    assert ("PUT", "/api/v1/settings/mcp-servers") in calls
    assert ("PUT", "/api/v1/settings/sandbox-providers") in calls
    assert ("POST", "/api/v1/agents") in calls


def test_bootstrap_updates_existing_agent():
    calls = []

    def handler(req):
        calls.append((req.method, req.url.path))
        if req.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "ag1", "name": "cloud-cost-janitor"}]})
        return httpx.Response(200, json={"data": {}})

    http = httpx.Client(base_url="http://tf", transport=httpx.MockTransport(handler))
    env = {"OPENAI_API_KEY": "sk", "OPENAI_MODEL_ID": "m", "DAYTONA_API_KEY": "dk",
           "MCP_PUBLIC_URL": "http://x/mcp", "AGENT_NAME": "cloud-cost-janitor"}
    bt.bootstrap("http://tf", env, http)
    assert ("PUT", "/api/v1/agents/ag1") in calls


def test_error_output_redacts_secrets():
    def handler(req: httpx.Request):
        if req.method == "PUT" and req.url.path == "/api/v1/settings/model-providers":
            return httpx.Response(400, json={"error": {"message": "bad key sk-SECRET123 / dk-SECRET456"}})
        return httpx.Response(200, json={"data": []})

    http = httpx.Client(base_url="http://tf", transport=httpx.MockTransport(handler))
    env = {"OPENAI_API_KEY": "sk-SECRET123", "OPENAI_MODEL_ID": "gpt-5.2", "DAYTONA_API_KEY": "dk-SECRET456",
           "MCP_PUBLIC_URL": "http://localhost:8000/mcp", "AGENT_NAME": "cloud-cost-janitor"}
    with pytest.raises(SystemExit) as excinfo:
        bt.bootstrap("http://tf", env, http)
    message = str(excinfo.value)
    assert "sk-SECRET123" not in message
    assert "dk-SECRET456" not in message
    assert "***" in message
