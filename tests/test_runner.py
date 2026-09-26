from types import SimpleNamespace

from api.runner import SessionRunner


class Ev(SimpleNamespace):
    def model_dump(self, mode="json"):
        return dict(vars(self))


def _turn1():
    return [
        Ev(type="turn.created", id="t1"),
        Ev(type="model.message", id="m1", thread_id="main", content="",
           tool_calls=[{"id": "c1", "function": {"name": "delete_volume", "arguments": '{"volume_id": "vol-1"}'}}]),
        Ev(type="tool.approval_required", id="a1", thread_id="main", tool_calls=[{"id": "c1", "source_event_id": "m1"}]),
        Ev(type="turn.done", id="d1", state={"status": "done", "output": None, "required_actions": [{"type": "tool.approval_required"}]}),
    ]


def _turn2():
    return [
        Ev(type="turn.created", id="t2"),
        Ev(type="turn.done", id="d2", state={"status": "done", "output": {"content": "Saved $4/mo"}, "required_actions": []}),
    ]


class FakeSessions:
    def __init__(self):
        self.turns = [_turn1(), _turn2()]
        self.inputs = []

    def create(self, agent):
        self.agent = agent
        return SimpleNamespace(data=SimpleNamespace(id="s1"))

    def create_turn_stream(self, session_id, input):
        self.inputs.append(input)
        return iter(self.turns.pop(0))


def test_runner_pauses_then_resumes_with_decisions():
    client = SimpleNamespace(sessions=FakeSessions())
    r = SessionRunner(client, "cloud-cost-janitor", loop=None)
    assert r.start("clean us-east-1") == "s1"
    r.wait(5)
    types = [e["type"] for e in r.buffer]
    assert types == ["status", "approval", "status"]
    assert r.buffer[-1]["status"] == "paused"
    assert r.pending[0]["tool"] == "delete_volume"

    r.decide([{"tool_call_id": "c1", "thread_id": "main", "allow": False, "reason": "keep it"}])
    r.wait(5)
    assert client.sessions.inputs[1] == [{"type": "user.tool_approval", "thread_id": "main", "tool_call_id": "c1",
                                          "approval": {"status": "deny", "reason": "keep it"}}]
    assert r.buffer[-2] == {"type": "done", "output": "Saved $4/mo"}
    assert [a["decision"] for a in r.audit] == ["requested", "denied"]
    assert r.pending == []


def test_stream_exception_becomes_error_status():
    class Boom(FakeSessions):
        def create_turn_stream(self, session_id, input):
            raise RuntimeError("tf down")
    r = SessionRunner(SimpleNamespace(sessions=Boom()), "a", loop=None)
    r.start("x")
    r.wait(5)
    assert r.buffer[-1] == {"type": "status", "status": "error", "message": "RuntimeError: tf down"}
