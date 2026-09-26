import asyncio

from conftest import REGION

from mcp_server import server


def _tools():
    return {t.name: t for t in asyncio.run(server.mcp.list_tools())}


def test_all_tools_registered():
    assert set(_tools()) == set(server.READ_TOOLS + server.WRITE_TOOLS + server.DESTRUCTIVE_TOOLS)


def test_destructive_annotations():
    tools = _tools()
    for name in server.DESTRUCTIVE_TOOLS:
        assert tools[name].annotations.destructiveHint is True, name
    for name in server.READ_TOOLS:
        assert tools[name].annotations.readOnlyHint is True, name
    assert tools["snapshot_volume"].annotations.destructiveHint is False
    assert tools["snapshot_volume"].annotations.readOnlyHint is False


def test_list_tool_wraps_items(ec2, az):
    vid = ec2.create_volume(AvailabilityZone=az, Size=8)["VolumeId"]
    out = server.list_unattached_volumes(REGION)
    assert out["region"] == REGION and vid in {i["id"] for i in out["items"]}


def test_errors_become_structured(monkeypatch):
    def boom(region):
        raise RuntimeError("no creds")
    monkeypatch.setattr(server.aws_scan, "list_unassociated_eips", boom)
    out = server.list_unassociated_eips(REGION)
    assert out == {"ok": False, "error": "RuntimeError: no creds"}
