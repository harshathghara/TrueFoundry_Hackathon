"""Translate TrueForge turn events (wire-format dicts) into the small event contract the UI consumes."""
import json
import re
from typing import Any

LIST_TOOLS = {"list_unattached_volumes", "list_stopped_instances", "list_idle_load_balancers",
              "list_unassociated_eips", "list_old_snapshots", "estimate_monthly_cost"}
SANDBOX_HINTS = ("sandbox", "bash", "shell", "exec", "python", "code", "file")
ID_ARGS = ("volume_id", "instance_id", "arn", "allocation_id", "snapshot_id", "resource_id")


def short_tool_name(call: dict) -> str:
    name = (call.get("tool_info") or {}).get("name") or call.get("function", {}).get("name", "")
    return re.split(r"__|/", name)[-1]


def parse_content(content: Any) -> Any:
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not isinstance(content, str):
        return content
    try:
        parsed = json.loads(content)
    except ValueError:
        return {"raw": content}
    if isinstance(parsed, list) and parsed and all(isinstance(p, dict) and p.get("type") == "text" for p in parsed):
        return parse_content(parsed)
    return parsed


def _args(call: dict) -> dict:
    raw = call.get("function", {}).get("arguments") or "{}"
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {"raw": raw}
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def find_call(index: dict[str, dict], call_id: str, source_event_id: str | None = None) -> dict | None:
    candidates = [index[source_event_id]] if source_event_id in index else index.values()
    for ev in candidates:
        if ev.get("type") == "model.message":
            for tc in ev.get("tool_calls") or []:
                if tc.get("id") == call_id:
                    return tc
    return None


def resource_id_from_args(args: dict) -> str | None:
    return next((args[k] for k in ID_ARGS if isinstance(args.get(k), str)), None)


def _kind(tool: str) -> str:
    return "sandbox" if any(h in tool for h in SANDBOX_HINTS) and not tool.startswith(("list_", "check_", "delete_", "snapshot_")) else "tool"


class Normalizer:
    def feed(self, event: dict, index: dict[str, dict]) -> list[dict]:
        t = event.get("type")
        if t == "turn.created":
            return [{"type": "status", "status": "running"}]
        if t == "model.message":
            return [{"type": "message", "id": event.get("id"), "content": event["content"]}] if event.get("content") else []
        if t == "tool.response":
            return self._tool_response(event, index)
        if t == "tool.approval_required":
            return self._approvals(event, index)
        if t == "sandbox.created":
            return [{"type": "step", "id": event.get("id"), "kind": "sandbox", "title": "Sandbox provisioned",
                     "detail": {"sandbox_id": event.get("sandbox_id")}}]
        if t == "thread.created":
            return [{"type": "step", "id": event.get("id"), "kind": "subagent", "title": event.get("title", "subagent"), "detail": {}}]
        if t == "turn.done":
            return self._done(event.get("state") or {})
        return []

    def _tool_response(self, event, index):
        call = find_call(index, event.get("tool_call_id"))
        tool = short_tool_name(call) if call else "tool"
        result = parse_content(event.get("content"))
        out = [{"type": "step", "id": event.get("id"), "kind": _kind(tool), "title": tool,
                "detail": {"args": _args(call) if call else {}, "result": result}}]
        if tool in LIST_TOOLS and isinstance(result, dict) and isinstance(result.get("items"), list):
            out.append({"type": "resources", "items": result["items"]})
        if tool == "check_blast_radius" and isinstance(result, dict) and "resource_id" in result:
            reasons = result.get("reasons")
            if result.get("safe"):
                label = "safe"
            elif isinstance(reasons, str) and reasons:
                label = reasons
            elif isinstance(reasons, list) and reasons:
                label = "; ".join(reasons)
            else:
                label = "unsafe"
            out.append({"type": "resources", "items": [{"id": result["resource_id"], "blast_radius": label,
                                                          "blast_warnings": result.get("warnings") or []}]})
        return out

    def _approvals(self, event, index):
        out = []
        for ref in event.get("tool_calls") or []:
            call = find_call(index, ref["id"], ref.get("source_event_id"))
            args = _args(call) if call else {}
            out.append({"type": "approval", "tool_call_id": ref["id"], "thread_id": event.get("thread_id") or "main",
                        "tool": short_tool_name(call) if call else "unknown", "args": args,
                        "resource_id": resource_id_from_args(args)})
        return out

    def _done(self, state):
        status = state.get("status")
        required_actions = state.get("required_actions")
        if status == "done" and required_actions:
            out = []
            if any(ra.get("type") != "tool.approval_required" for ra in required_actions):
                out.append({"type": "message", "id": "needs-input",
                            "content": "The agent is waiting for input it can't get here — "
                                       "open TrueForge at http://localhost:8790 to answer."})
            out.append({"type": "status", "status": "paused"})
            return out
        if status == "done":
            raw_output = state.get("output")
            if isinstance(raw_output, dict):
                output = raw_output.get("content") or ""
            elif isinstance(raw_output, str):
                output = raw_output
            else:
                output = ""
            return [{"type": "done", "output": output}, {"type": "status", "status": "done"}]
        message = state.get("message") or state.get("reason") or status
        return [{"type": "status", "status": "error", "message": message}]
