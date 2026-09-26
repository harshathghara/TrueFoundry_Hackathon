"""Drives one TrueForge session: streams turns in a background thread and fans events out to SSE subscribers."""
import asyncio
import json
import os
import threading
from datetime import datetime, timezone

from api.events import Normalizer


def _to_dict(ev) -> dict:
    if hasattr(ev, "model_dump"):
        return ev.model_dump(mode="json")
    if hasattr(ev, "dict"):
        return ev.dict()
    return dict(ev)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SessionRunner:
    def __init__(self, client, agent_name: str, loop: asyncio.AbstractEventLoop | None):
        self.client = client
        self.agent_name = agent_name
        self.loop = loop
        self.session_id: str | None = None
        self.buffer: list[dict] = []
        self.audit: list[dict] = []
        self.pending: list[dict] = []
        self._subscribers: set[asyncio.Queue] = set()
        self._objects: dict[str, object] = {}
        self._index: dict[str, dict] = {}
        self._normalizer = Normalizer()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self, prompt: str) -> str:
        session = self.client.sessions.create(agent={"name": self.agent_name})
        self.session_id = session.data.id
        self._run_turn([{"type": "user.message", "content": prompt}])
        return self.session_id

    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def decide(self, decisions: list[dict]) -> None:
        if self.is_busy():
            raise RuntimeError("turn still running")
        if not self.pending:
            raise RuntimeError("no pending approvals")
        items = []
        by_call = {p["tool_call_id"]: p for p in self.pending}
        for d in decisions:
            approval = {"status": "allow"} if d["allow"] else {"status": "deny", "reason": d.get("reason") or "denied by operator"}
            items.append({"type": "user.tool_approval", "thread_id": d["thread_id"], "tool_call_id": d["tool_call_id"], "approval": approval})
            p = by_call.get(d["tool_call_id"], {})
            self.audit.append({"at": _now(), "tool": p.get("tool"), "resource_id": p.get("resource_id"),
                               "decision": "approved" if d["allow"] else "denied", "reason": d.get("reason")})
        self.pending = []
        self._publish({"type": "status", "status": "running"})
        self._run_turn(items)

    def wait(self, timeout: float) -> None:
        if self._thread:
            self._thread.join(timeout)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            for e in self.buffer:
                q.put_nowait(e)
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def _run_turn(self, input_items: list[dict]) -> None:
        self._thread = threading.Thread(target=self._consume, args=(input_items,), daemon=True)
        self._thread.start()

    def _consume(self, input_items: list[dict]) -> None:
        self._turn_event_ids: list[str] = []
        try:
            stream = self.client.sessions.create_turn_stream(session_id=self.session_id, input=input_items)
            for ev in stream:
                self._handle(ev)
        except Exception as e:  # noqa: BLE001 — surface any SDK/network failure to the UI
            self._publish({"type": "status", "status": "error", "message": f"{type(e).__name__}: {e}"})
            return
        dump = os.getenv("JANITOR_DUMP_EVENTS")
        if dump:  # capture fully-merged events (deltas folded in) to lock normalizer tests to TrueForge's actual shapes
            with open(dump, "a", encoding="utf-8") as f:
                for eid in self._turn_event_ids:
                    f.write(json.dumps(self._index[eid], default=str) + "\n")

    def _handle(self, ev) -> None:
        if getattr(ev, "type", None) == "model.message.delta":
            from trueforge_sdk.events import merge_event_delta
            base = self._objects.get(ev.id)
            if base is None:
                return
            merge_event_delta(base, ev)
            event = _to_dict(base)
        else:
            self._objects[ev.id] = ev
            event = _to_dict(ev)
            self._turn_event_ids.append(event["id"])
        self._index[event["id"]] = event
        for out in self._normalizer.feed(event, self._index):
            if out["type"] == "approval":
                self.pending.append(out)
                self.audit.append({"at": _now(), "tool": out["tool"], "resource_id": out["resource_id"], "decision": "requested"})
            self._publish(out)

    def _publish(self, out: dict) -> None:
        with self._lock:
            self.buffer.append(out)
            subscribers = list(self._subscribers)
        if self.loop is None:
            return
        for q in subscribers:
            self.loop.call_soon_threadsafe(q.put_nowait, out)
