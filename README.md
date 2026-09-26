# 🧹 Cloud Cost Janitor

An agent that **acts**: it finds idle AWS resources, prices them, builds a teardown plan in a sandbox,
checks blast radius, and deletes **only what a human approves**. Built on
[TrueForge](https://github.com/truefoundry/trueforge) for the *Agents That Act* hackathon (TrueFoundry × Polaris). MIT licensed.

## The problem
Cloud accounts collect waste: unattached EBS volumes, stopped instances still paying for disks, load
balancers with no targets, idle Elastic IPs, stale snapshots. Finding, pricing and safely removing them is
recurring toil an engineer would hand off — if nothing gets deleted without their sign-off.

## What the agent reaches
A real AWS account through our MCP server `aws-janitor` (`mcp_server/`, boto3): EC2 volumes, instances,
Elastic IPs, snapshots, ELBv2 load balancers, and Route 53 records (read-only, for blast radius).
AWS credentials live only in the MCP server process — the model and the sandbox never see them.
Blast-radius checks on load balancers also report any remaining listeners as warnings (non-blocking).

## Where it stops
| Action | Gate |
|---|---|
| list / price / blast-radius | Runs autonomously (read-only) |
| `snapshot_volume` | Runs autonomously — additive and reversible — but refuses untagged or `env=prod` volumes |
| `delete_volume`, `terminate_instance`, `delete_load_balancer`, `release_eip`, `delete_snapshot` | **TrueForge pauses for human approval** every time |

Layers behind the approval gate:
1. MCP `destructiveHint: true` → TrueForge `@destructive` gate, plus every delete tool listed by name in `require_approval_for_tools`.
2. In-tool rail: refuses anything not tagged `janitor-demo=true`.
3. In-tool rail: **always** refuses anything tagged `env=prod` — even if it also carries the demo tag. This is our check, not IAM's.
4. EC2 `DryRun=True` before each real EC2 delete.
5. IAM: the `cost-janitor` user may only stop or delete resources tagged `janitor-demo=true`. IAM does **not** block prod; layer 3 does.

## Architecture
```
React (5173) → FastAPI bridge (8080) → trueforge-sdk → TrueForge (8790) → TrueFoundry AI Gateway · Daytona sandbox · MCP aws-janitor (8000) → AWS
```

## How TrueForge is used
- **Agent loop & model:** the `cloud-cost-janitor` agent (spec in `agent/`) runs on TrueForge, registered by `scripts/bootstrap_trueforge.py` via TrueForge's HTTP API. The model provider is selectable via `MODEL_PROVIDER`: set it to `gateway` and the model runs through the **TrueFoundry AI Gateway**, registered as a custom OpenAI-compatible provider `gpt-model/openai` proxying to the gateway model id `vm-polaris/openai` (served by `gpt-4o-mini`). OpenAI-direct is kept as a fallback — `MODEL_PROVIDER=openai` (the default, unchanged from before) registers the model as `openai/janitor-model`, backed by the real OpenAI model id from `OPENAI_MODEL_ID` (`gpt-5.5` for our demo run).
- **Tools:** our MCP server is attached as a remote connector; TrueForge calls the tools.
- **Sandbox:** the agent writes and runs Python in TrueForge's Daytona sandbox to rank costs and produce `teardown-plan.md` / `.csv`.
- **Human checkpoints:** TrueForge emits `tool.approval_required`; our bridge resumes the turn with `user.tool_approval` allow/deny decisions from the dashboard. The dashboard only submits decisions once the agent has paused for approval, and if a submit fails the approval cards stay on screen so you can resubmit. The same agent also works in TrueForge's own chat UI.

## Real vs mocked
| Real | Mocked / simulated |
|---|---|
| AWS resources created by `scripts/seed_aws.py` in a live account | Unit tests use `moto` (in-memory AWS) — no real calls |
| Every MCP tool call against AWS during the demo | Prices come from a static us-east-1 table, not Cost Explorer or the Pricing API |
| The sandbox Python run and plan files | "Idle" = state signals (unattached, stopped, zero targets, unassociated), not 14-day CloudWatch metrics |
| Approved deletes (they really delete) | Snapshot age threshold is 0 days in the demo (`JANITOR_SNAPSHOT_MIN_AGE_DAYS`) so fresh seeds show up |
| OpenAI model calls through TrueForge | The dry-run path is AWS's `DryRun` validation, not an executed delete |

## Known limits
- One region per run, one account; no multi-account fan-out.
- Static prices (us-east-1 list prices); other regions fall back to them.
- Snapshot cost is an upper bound (full volume size; snapshots are incremental).
- Audit log is in memory; restarting the API loses it.
- Destructive actions only touch `janitor-demo=true` resources by design; running on real waste means changing `JANITOR_REQUIRE_TAG` deliberately.
- The MCP server has no auth; it binds to 127.0.0.1 only. Tag and prod rails still apply to any caller.

## Run it (≈10 minutes)
Prereqs: Node ≥ 22.14, Python ≥ 3.11, an AWS account with a default VPC, an OpenAI key OR a TrueFoundry Gateway key, a Daytona key with `write:sandboxes`, `write:snapshots` and `delete:snapshots` (the default quick-start key is not enough).
```bash
cp .env.example .env                                  # fill in keys
# once per AWS account, with ADMIN credentials (the least-privilege app user cannot create IAM roles):
aws iam create-service-linked-role --aws-service-name elasticloadbalancing.amazonaws.com
aws iam create-user --user-name cost-janitor && aws iam put-user-policy --user-name cost-janitor --policy-name cloud-cost-janitor --policy-document file://scripts/iam-policy.json
aws iam create-access-key --user-name cost-janitor   # put these keys in .env
# The admin-only IAM step above uses your admin AWS profile; the app itself only ever
# reads the cost-janitor keys from .env.
python -m venv .venv
source .venv/Scripts/activate                         # Git Bash · PowerShell: .venv\Scripts\Activate.ps1 · macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

# Terminal 1 (new terminal, repo root) → http://localhost:8790 (TrueForge blocks localhost MCP URLs unless allowed):
OUTBOUND_URL_ALLOWED_HOSTS='["localhost","127.0.0.1"]' npx @truefoundry/trueforge@0.2.1
#   PowerShell: $env:OUTBOUND_URL_ALLOWED_HOSTS='["localhost","127.0.0.1"]'; npx @truefoundry/trueforge@0.2.1

# Terminal 2 (new terminal, repo root, venv activated) → http://localhost:8000/mcp
python -m mcp_server.server

# Terminal 3 (new terminal, repo root, venv activated): register the agent and seed demo
# waste first, then start the API bridge in the same terminal once they finish
python -m scripts.bootstrap_trueforge                  # registers model, MCP server, sandbox, agent
python -m scripts.seed_aws                             # creates tagged demo waste (a few minutes)
uvicorn api.main:app --port 8080

# Terminal 4 (new terminal, repo root, venv activated) → http://localhost:5173
cd web && npm install && npm run dev
```
Click **Run janitor** → watch the steps → approve / deny → read the report. Or open http://localhost:8790,
pick the `cloud-cost-janitor` agent, and ask it to clean up us-east-1.
Afterwards: `python -m scripts.cleanup_aws`.

Tests (no AWS needed): `pytest` and `cd web && npm test`.

## AI assistants used
Claude Code (Anthropic) helped with planning and implementation. The team reviewed every line and can walk through the architecture.

## Next steps
Multi-region fan-out, Cost Explorer-backed pricing, weekly runs via TrueForge Schedules, Slack approvals.
