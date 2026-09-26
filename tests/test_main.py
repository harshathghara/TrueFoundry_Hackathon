from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import main


class FakeRunner:
    def __init__(self, client, agent_name, loop):
        self.decided = None
        self.audit = [{"decision": "requested"}]

    def start(self, prompt):
        self.prompt = prompt
        return "s1"

    def decide(self, decisions):
        self.decided = decisions


def test_scan_decide_audit(monkeypatch):
    monkeypatch.setattr(main, "SessionRunner", FakeRunner)
    monkeypatch.setattr(main, "get_client", lambda: None)
    main.RUNNERS.clear()
    c = TestClient(main.app)
    assert c.post("/api/scan", json={"region": "us-east-1"}).json() == {"session_id": "s1"}
    assert "us-east-1" in main.RUNNERS["s1"].prompt
    body = {"decisions": [{"tool_call_id": "c1", "thread_id": "main", "allow": True}]}
    assert c.post("/api/sessions/s1/decisions", json=body).json() == {"ok": True}
    assert main.RUNNERS["s1"].decided == [{"tool_call_id": "c1", "thread_id": "main", "allow": True, "reason": None}]
    assert c.get("/api/sessions/s1/audit").json() == {"audit": [{"decision": "requested"}]}


def test_unknown_session_404():
    main.RUNNERS.clear()
    assert TestClient(main.app).get("/api/sessions/nope/audit").status_code == 404


class BusyRunner(FakeRunner):
    def decide(self, decisions):
        raise RuntimeError("turn still running")


def test_decide_conflict_returns_409(monkeypatch):
    monkeypatch.setattr(main, "SessionRunner", BusyRunner)
    monkeypatch.setattr(main, "get_client", lambda: None)
    main.RUNNERS.clear()
    c = TestClient(main.app)
    c.post("/api/scan", json={"region": "us-east-1"})
    body = {"decisions": [{"tool_call_id": "c1", "thread_id": "main", "allow": True}]}
    resp = c.post("/api/sessions/s1/decisions", json=body)
    assert resp.status_code == 409
    assert resp.json() == {"detail": "turn still running"}
