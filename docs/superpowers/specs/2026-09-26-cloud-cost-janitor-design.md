# Cloud Cost Janitor — Design Spec

**Date:** 2026-09-26 · **Event:** Agents That Act — TrueFoundry × Polaris Hackathon (build 12:00–19:00 IST)
**Theme:** Cloud Cost Janitor · **Stack:** TrueForge (agent harness) · OpenAI (model) · AWS (real system) · Python + React

## 1. Problem & job

Cloud accounts accumulate waste: unattached EBS volumes, stopped EC2 instances (still paying for EBS),
load balancers with no targets, unassociated Elastic IPs, and stale snapshots. Finding them, pricing them,
and cleaning them up safely is tedious work an engineer would happily delegate — **as long as nothing
is deleted without their sign-off.**

**The one job, end to end:** scan an AWS region → price each idle resource per month → produce a
teardown plan → check blast radius → pause for human approval on every delete → snapshot first where
reversible → delete what was approved → report $/month saved and what was denied.

## 2. How this maps to the judging rubric

| Criterion (pts) | How we score it |
|---|---|
| Harness does the work (30) | TrueForge runs the loop, calls our MCP tools against real AWS, executes generated Python in its Daytona sandbox to build the plan, and holds destructive calls for approval. |
| Actually runs (25) | `seed_aws.py` creates tagged waste in any account; `bootstrap_trueforge.py` configures TrueForge via its HTTP API; README is copy-paste runnable; tests use `moto` (no creds needed). |
| Approval gates (20) | Deletes/terminates/releases are MCP-annotated `destructiveHint: true` **and** listed by name in `require_approval_for_tools`. Approval card shows resource, $/mo, blast radius, and whether a snapshot exists. Snapshot (reversible) runs without a gate — we explain why. |
| Job worth delegating (15) | FinOps cleanup is recurring toil with real $ attached. |
| Demo clarity (10) | One button → live agent steps → plan → approve one / deny one → savings summary. |

## 3. Architecture

```
React + Vite + Tailwind (web/, :5173)
      │  REST + SSE
      ▼
FastAPI "janitor-api" (api/, :8080) ──trueforge-sdk──►  TrueForge server (npx @truefoundry/trueforge, :8790)
                                                            ├─ model: OpenAI (provider registered via API)
                                                            ├─ sandbox: Daytona (cost math, plan files)
                                                            └─ MCP (remote, streamable HTTP)
                                                                   ▼
                                                     FastMCP "aws-janitor" (mcp_server/, :8000/mcp) ──boto3──► AWS
```

All four processes run locally. TrueForge reaches our MCP server over `http://localhost:8000/mcp`.
AWS credentials live **only** in the MCP server's environment; the sandbox and the model never see them.

## 4. Components

### 4.1 `mcp_server/` — FastMCP server (Python, boto3)

Exposes AWS as MCP tools over streamable HTTP. Each tool returns JSON-serializable dicts.

| Tool | Annotation | Purpose |
|---|---|---|
| `list_unattached_volumes(region)` | readOnly | EBS volumes in `available` state: id, size, type, age_days, tags |
| `list_stopped_instances(region)` | readOnly | EC2 in `stopped` state: id, type, attached volumes, stopped_since |
| `list_idle_load_balancers(region)` | readOnly | ALB/NLB whose target groups have zero registered targets |
| `list_unassociated_eips(region)` | readOnly | Elastic IPs without an association |
| `list_old_snapshots(region, older_than_days=30)` | readOnly | Self-owned snapshots older than N days, flagged if used by an AMI |
| `estimate_monthly_cost(resources)` | readOnly | Static per-region price table (`pricing.py`) → $/mo per resource + total |
| `check_blast_radius(resource_id)` | readOnly | Dependencies: AMIs referencing a snapshot, instances using a volume, listeners/Route 53 records pointing at an LB, tags like `env=prod` |
| `snapshot_volume(volume_id)` | write (not destructive) | Creates a backup snapshot before deletion; reversible, not gated |
| `delete_volume(volume_id)` | **destructive** | Gated |
| `terminate_instance(instance_id)` | **destructive** | Gated |
| `delete_load_balancer(arn)` | **destructive** | Gated |
| `release_eip(allocation_id)` | **destructive** | Gated |
| `delete_snapshot(snapshot_id)` | **destructive** | Gated |

**Safety rails inside every destructive tool** (defense in depth, independent of the harness gate):
1. Refuse unless the resource has tag `janitor-demo=true` (configurable via `JANITOR_REQUIRE_TAG`; set empty to disable).
2. Call AWS with `DryRun=True` first where the API supports it; surface permission errors cleanly.
3. Return a structured result `{ok, resource_id, action, error?}` — never raise raw boto errors to the model.

Cost estimation uses a static price table for the demo region (us-east-1 default: gp3 $0.08/GB-mo,
gp2 $0.10/GB-mo, snapshot $0.05/GB-mo, idle EIP $3.60/mo, ALB ~$16.43/mo base). Rationale: Cost
Explorer lags ~24h and bills per call; freshly seeded resources have no billing history.

### 4.2 `api/` — FastAPI bridge (Python, `trueforge-sdk`)

| Endpoint | Behavior |
|---|---|
| `POST /api/scan` `{region}` | Open a TrueForge session on the saved agent `cloud-cost-janitor`, start a turn with the scan prompt, return `{session_id}`. |
| `GET /api/sessions/{id}/events` | SSE relay of normalized events (see 4.4) for the current turn. |
| `POST /api/sessions/{id}/decisions` `{decisions:[{tool_call_id, thread_id, allow, reason?}]}` | Resume the paused turn with `user.tool_approval` items; stream continues on the same SSE channel. |
| `GET /api/sessions/{id}/audit` | In-memory audit log: every approval request and decision with timestamp. |
| `GET /api/health` | Checks TrueForge and MCP server reachability. |

A per-session `TurnRunner` runs the SDK stream in a background thread, keeps the id-keyed event index
(merging deltas with `merge_event_delta`), resolves each `tool.approval_required` ref to the tool name
and arguments via its `source_event_id`, and publishes normalized events to an `asyncio.Queue` per subscriber.

### 4.3 `web/` — React + Vite + Tailwind dashboard

Single page:
- **Header KPI strip:** resources found · monthly waste $ · approved savings $ · pending approvals.
- **Scan panel:** region select + "Run janitor" button.
- **Agent feed:** live list of steps (tool calls, sandbox runs, messages) from SSE.
- **Resource table:** type, id, $/mo, age, blast-radius badge.
- **Approval cards:** one per pending destructive call — tool, resource, $/mo, blast radius, snapshot status, Approve / Deny (+ reason). All pending decisions are submitted together (TrueForge resumes a turn with all decisions at once).
- **Teardown plan:** markdown rendered from the agent's final message.
- **Audit trail:** decisions with timestamps.

### 4.4 Normalized event contract (api → web)

```json
{"type": "status",    "status": "running|paused|done|error"}
{"type": "step",      "id": "...", "kind": "tool|sandbox|message|subagent", "title": "...", "detail": {}}
{"type": "message",   "id": "...", "content": "markdown (accumulated)"}
{"type": "approval",  "tool_call_id": "...", "thread_id": "...", "tool": "delete_volume", "args": {}}
{"type": "resources", "items": [{"id": "...", "kind": "ebs", "monthly_cost": 8.0, "blast_radius": "none"}]}
{"type": "done",      "output": "final markdown"}
```

`resources` is derived by the api from `tool.response` events of the `list_*` / `estimate_monthly_cost` tools.

### 4.5 `agent/` — agent spec & instructions

`agent/manifest.json` is the TrueForge agent spec saved as `cloud-cost-janitor`:
- `model`: `openai/<model>` (name from `OPENAI_MODEL`, default `gpt-5.2`), `temperature: 0.1`.
- `mcp_servers`: `[{name: "aws-janitor", enable_tools: ["@all"], preload: true, require_approval_for_tools: ["@destructive", "delete_volume", "terminate_instance", "delete_load_balancer", "release_eip", "delete_snapshot"]}]`.
- `config`: sandbox enabled, generative_ui disabled (our UI renders), ask_user_questions enabled, dynamic_sub_agents disabled (keeps the stream simple), iteration_limit 60.

`agent/instructions.md` (system prompt): the procedure — scan all five categories, call
`estimate_monthly_cost`, use the sandbox to write & run Python that aggregates costs and writes
`teardown-plan.md` + `teardown-plan.csv`, call `check_blast_radius` for each candidate, never propose
deleting anything with non-empty blast radius or `env=prod`, snapshot volumes before deleting them,
then call destructive tools one per resource, respect denials, and finish with a summary table.

### 4.6 `scripts/`

- `bootstrap_trueforge.py` — idempotent: upserts the OpenAI model provider, the `aws-janitor` remote MCP
  server, the Daytona sandbox provider, and the `cloud-cost-janitor` agent via the TrueForge HTTP API
  (`/api/v1/settings/model-providers`, `/api/v1/settings/mcp-servers`, `/api/v1/settings/sandbox-providers`, `/api/v1/agents`).
- `seed_aws.py` — creates tagged (`janitor-demo=true`) waste: 2 unattached gp3 volumes, 1 stopped
  t3.micro, 1 ALB with an empty target group, 1 unassociated EIP, 1 snapshot. Plus one decoy volume tagged
  `env=prod` to show the agent refusing to propose it.
- `cleanup_aws.py` — deletes everything tagged `janitor-demo=true` (for teardown after the demo).
- `iam-policy.json` — least-privilege policy for the MCP server's IAM user.

## 5. Data flow (demo run)

1. User clicks **Run janitor** (us-east-1) → `POST /api/scan` → TrueForge session + turn.
2. Agent calls the five `list_*` tools (no pause), then `estimate_monthly_cost`.
3. Agent writes and runs Python in the Daytona sandbox → plan files + totals.
4. Agent calls `check_blast_radius` per candidate; skips the `env=prod` decoy with a stated reason.
5. Agent calls `snapshot_volume` (runs), then `delete_volume` etc. → TrueForge emits `tool.approval_required`, turn ends paused.
6. UI shows approval cards. Human approves some and denies one with a reason → `POST /decisions`.
7. Turn resumes: approved tools execute against AWS; denied ones return the denial to the model.
8. Agent's final message: summary table, $/mo saved, what was denied and why. UI updates KPIs + audit.

## 6. Error handling

- AWS errors → structured `{ok:false, error}` tool results; the agent reports rather than retries.
- Tag rail refusal → `{ok:false, error:"refused: resource not tagged janitor-demo=true"}`.
- TrueForge/MCP unreachable → `/api/health` red status in the UI; scan button disabled.
- SSE disconnect → client reconnects; api replays buffered normalized events for the session.
- Turn ends with `status: error` → UI shows the error and a "retry" button that starts a new turn in the same session.

## 7. Testing

- `mcp_server` tools: pytest + `moto` (`mock_aws`) — list/detect logic, pricing math, tag rail, dry-run path. Runs with no AWS credentials.
- `api`: unit tests for the event normalizer and approval-ref resolution using recorded event fixtures.
- End to end (manual, live): `seed_aws.py` → bootstrap → run in UI → approve/deny → `cleanup_aws.py`.

## 8. Out of scope (YAGNI)

Multi-account/multi-region fan-out, Cost Explorer integration, auth/OIDC, persistence beyond memory,
scheduling, Terraform output, Slack notifications. Mention as "next steps" in the README only.

## 9. Submission checklist

- Public repo with working README (setup in ≤ 10 commands) and an "AI assistants used" section.
- No secrets: `.env` git-ignored, `.env.example` committed.
- Demo shows code running in the sandbox and the agent stopping before an irreversible action.
- Community post on LinkedIn/X tagging @truefoundry and @polariscodes.
