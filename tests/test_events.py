import json
from pathlib import Path

import pytest

from api.events import Normalizer, parse_content, short_tool_name

FIXTURE = Path(__file__).parent / "fixtures" / "real_turn.jsonl"


def _msg(mid, calls=(), content=""):
    return {"type": "model.message", "id": mid, "thread_id": "main", "content": content,
            "tool_calls": [{"id": cid, "function": {"name": name, "arguments": json.dumps(args)}} for cid, name, args in calls]}


def test_short_tool_name_strips_prefixes():
    assert short_tool_name({"function": {"name": "aws-janitor__delete_volume"}}) == "delete_volume"
    assert short_tool_name({"function": {"name": "x"}, "tool_info": {"name": "list_old_snapshots"}}) == "list_old_snapshots"


def test_parse_content_handles_mcp_text_blocks():
    assert parse_content('{"a": 1}') == {"a": 1}
    assert parse_content([{"type": "text", "text": '{"a": 2}'}]) == {"a": 2}
    assert parse_content('[{"type":"text","text":"{\\"a\\": 3}"}]') == {"a": 3}
    assert parse_content("not json") == {"raw": "not json"}


def test_message_content_emitted():
    n, idx = Normalizer(), {}
    m = _msg("m1", content="Scanning…")
    idx["m1"] = m
    assert n.feed(m, idx) == [{"type": "message", "id": "m1", "content": "Scanning…"}]


def test_tool_response_emits_step_and_resources():
    n, idx = Normalizer(), {}
    m = _msg("m1", [("c1", "list_unattached_volumes", {"region": "us-east-1"})])
    idx["m1"] = m
    resp = {"type": "tool.response", "id": "r1", "tool_call_id": "c1",
            "content": json.dumps({"region": "us-east-1", "items": [{"kind": "ebs", "id": "vol-1", "size_gb": 50}]})}
    out = n.feed(resp, idx)
    assert out[0]["type"] == "step" and out[0]["kind"] == "tool" and out[0]["title"] == "list_unattached_volumes"
    assert out[1] == {"type": "resources", "items": [{"kind": "ebs", "id": "vol-1", "size_gb": 50}]}


def test_estimate_and_blast_radius_become_resource_updates():
    n, idx = Normalizer(), {}
    idx["m1"] = _msg("m1", [("c1", "estimate_monthly_cost", {}), ("c2", "check_blast_radius", {"resource_id": "vol-9"})])
    est = n.feed({"type": "tool.response", "id": "r1", "tool_call_id": "c1",
                  "content": json.dumps({"items": [{"id": "vol-1", "kind": "ebs", "monthly_cost": 4.0}], "total_monthly_cost": 4.0})}, idx)
    assert est[-1] == {"type": "resources", "items": [{"id": "vol-1", "kind": "ebs", "monthly_cost": 4.0}]}
    br = n.feed({"type": "tool.response", "id": "r2", "tool_call_id": "c2",
                 "content": json.dumps({"resource_id": "vol-9", "safe": False, "reasons": ["tagged env=prod"], "warnings": []})}, idx)
    assert br[-1] == {"type": "resources", "items": [{"id": "vol-9", "blast_radius": "tagged env=prod", "blast_warnings": []}]}


def test_blast_radius_warnings_carried_to_resource():
    n, idx = Normalizer(), {}
    idx["m1"] = _msg("m1", [("c1", "check_blast_radius", {"resource_id": "arn-1"})])
    out = n.feed({"type": "tool.response", "id": "r1", "tool_call_id": "c1",
                  "content": json.dumps({"resource_id": "arn-1", "safe": True, "reasons": [],
                                          "warnings": ["listener HTTP:80 still configured"]})}, idx)
    assert out[-1] == {"type": "resources",
                        "items": [{"id": "arn-1", "blast_radius": "safe", "blast_warnings": ["listener HTTP:80 still configured"]}]}


def test_sandbox_tool_classified():
    n, idx = Normalizer(), {}
    idx["m1"] = _msg("m1", [("c1", "sandbox_exec", {"command": "python plan.py"})])
    out = n.feed({"type": "tool.response", "id": "r1", "tool_call_id": "c1", "content": "done"}, idx)
    assert out[0]["kind"] == "sandbox"


def test_approval_resolved_from_source_message():
    n, idx = Normalizer(), {}
    idx["m1"] = _msg("m1", [("c9", "delete_volume", {"volume_id": "vol-1"})])
    ev = {"type": "tool.approval_required", "id": "a1", "thread_id": "main", "tool_calls": [{"id": "c9", "source_event_id": "m1"}]}
    assert n.feed(ev, idx) == [{"type": "approval", "tool_call_id": "c9", "thread_id": "main", "tool": "delete_volume",
                                "args": {"volume_id": "vol-1"}, "resource_id": "vol-1"}]


def test_turn_done_paused_vs_done_vs_error():
    n = Normalizer()
    paused = {"type": "turn.done", "id": "d", "state": {"status": "done", "output": None, "required_actions": [{"type": "tool.approval_required"}]}}
    assert n.feed(paused, {}) == [{"type": "status", "status": "paused"}]
    done = {"type": "turn.done", "id": "d", "state": {"status": "done", "output": {"content": "## Summary"}, "required_actions": []}}
    assert n.feed(done, {}) == [{"type": "done", "output": "## Summary"}, {"type": "status", "status": "done"}]
    err = {"type": "turn.done", "id": "d", "state": {"status": "error", "message": "boom"}}
    assert n.feed(err, {}) == [{"type": "status", "status": "error", "message": "boom"}]


def test_turn_done_paused_with_non_approval_required_action_emits_message():
    n = Normalizer()
    paused = {"type": "turn.done", "id": "d", "state": {"status": "done", "output": None,
              "required_actions": [{"type": "tool.response_required"}]}}
    assert n.feed(paused, {}) == [
        {"type": "message", "id": "needs-input",
         "content": "The agent is waiting for input it can't get here — open TrueForge at http://localhost:8790 to answer."},
        {"type": "status", "status": "paused"},
    ]


def test_lifecycle_events():
    n = Normalizer()
    assert n.feed({"type": "turn.created", "id": "t"}, {}) == [{"type": "status", "status": "running"}]
    assert n.feed({"type": "sandbox.created", "id": "s", "sandbox_id": "sb1"}, {})[0]["kind"] == "sandbox"
    assert n.feed({"type": "thread.created", "id": "th", "title": "pricing"}, {})[0]["kind"] == "subagent"
    assert n.feed({"type": "mcp.initialize", "id": "i"}, {}) == []


def test_turn_done_with_string_output():
    n = Normalizer()
    done = {"type": "turn.done", "id": "d", "state": {"status": "done", "output": "plain", "required_actions": []}}
    assert n.feed(done, {}) == [{"type": "done", "output": "plain"}, {"type": "status", "status": "done"}]


def test_tool_response_with_non_mapping_arguments_does_not_raise():
    n, idx = Normalizer(), {}
    idx["m1"] = {"type": "model.message", "id": "m1", "thread_id": "main", "content": "",
                 "tool_calls": [{"id": "c1", "function": {"name": "delete_volume", "arguments": [1, 2, 3]}}]}
    out = n.feed({"type": "tool.response", "id": "r1", "tool_call_id": "c1", "content": "ok"}, idx)
    assert out[0]["detail"]["args"] == {}


def test_blast_radius_reasons_as_string():
    n, idx = Normalizer(), {}
    idx["m1"] = _msg("m1", [("c1", "check_blast_radius", {"resource_id": "vol-9"})])
    out = n.feed({"type": "tool.response", "id": "r1", "tool_call_id": "c1",
                  "content": json.dumps({"resource_id": "vol-9", "safe": False, "reasons": "tagged env=prod"})}, idx)
    assert out[-1] == {"type": "resources", "items": [{"id": "vol-9", "blast_radius": "tagged env=prod", "blast_warnings": []}]}


def test_tool_response_missing_id_does_not_raise():
    n, idx = Normalizer(), {}
    idx["m1"] = _msg("m1", [("c1", "list_unattached_volumes", {"region": "us-east-1"})])
    out = n.feed({"type": "tool.response", "tool_call_id": "c1", "content": json.dumps({"items": []})}, idx)
    assert out[0]["id"] is None


@pytest.mark.skipif(not FIXTURE.exists(), reason="capture a real stream first (Task 9 Step 9)")
def test_real_stream_fixture():
    n, idx, out = Normalizer(), {}, []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        idx[ev["id"]] = ev
        out += n.feed(ev, idx)
    approvals = [e for e in out if e["type"] == "approval"]
    assert approvals, "real stream produced no approval events"
    assert all(a["tool"] in {"delete_volume", "terminate_instance", "delete_load_balancer", "release_eip", "delete_snapshot"} for a in approvals)
    assert all(a["resource_id"] for a in approvals)
    assert any(e["type"] == "resources" and any("monthly_cost" in i for i in e["items"]) for e in out)
    assert any(e["type"] == "step" and e["kind"] == "sandbox" for e in out)
