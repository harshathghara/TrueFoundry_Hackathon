# Cloud Cost Janitor

An agent that **acts**: it finds idle AWS resources, prices them, writes a teardown plan, and deletes **only what a human approves**. Built on [TrueForge](https://github.com/truefoundry/trueforge) for the *Agents That Act* hackathon (TrueFoundry × Polaris). MIT licensed.

## The problem

Cloud accounts collect waste: unattached EBS volumes, stopped instances that still pay for disks, load balancers with no targets, idle Elastic IPs, and stale snapshots. Finding them, pricing them, and removing them is recurring toil — as long as nothing is deleted without a sign-off.

## What the agent reaches

A real AWS account, through our MCP server `aws-janitor` (`mcp_server/`, boto3): EC2 volumes, instances, Elastic IPs, snapshots, ELBv2 load balancers, and Route 53 records (read-only, for blast radius). AWS credentials live only in the MCP process. The model and the Daytona sandbox never see them.

Junk is a fixed rule, not a model guess: volume status `available`, instance state `stopped`, a load balancer with zero targets, an Elastic IP with no association, or a self-owned snapshot older than `JANITOR_SNAPSHOT_MIN_AGE_DAYS`.

## Where it stops

| Action | Gate |
|---|---|
| list / price / blast-radius | Runs on its own (read-only) |
| `snapshot_volume` | Runs on its own, but refuses untagged or `env=prod` volumes |
| `delete_volume`, `terminate_instance`, `delete_load_balancer`, `release_eip`, `delete_snapshot` | **TrueForge pauses for Allow / Deny** every time |

Behind that pause:

1. MCP `destructiveHint: true`, plus each delete tool named in `require_approval_for_tools`.
2. The tool refuses anything without the tag `janitor-demo=true`.
3. The tool always refuses `env=prod` or `env=production`, even when the demo tag is also present. IAM does not do this check.
4. EC2 `DryRun=True` before each real EC2 delete.
5. The `cost-janitor` IAM user may delete only resources tagged `janitor-demo=true`.

Blast radius also skips a candidate when a volume is attached, a snapshot backs an AMI, termination protection is on, an Elastic IP is associated, or a listener or Route 53 alias still points at a load balancer.

## Architecture

TrueForge's own UI and the `cloud-cost-janitor` agent both run in the local TrueForge process (`http://localhost:8790`). The UI sends the message to that agent. The agent does not run inside the sandbox.

```text
You → TrueForge UI + agent (:8790)
        ├─ model call → TrueFoundry AI Gateway → LLM
        ├─ AWS tools  → MCP aws-janitor (:8000) → AWS
        └─ plan script → Daytona sandbox (teardown-plan.md / .csv only)

Optional dashboard: React (:5173) → FastAPI (:8080) → the same TrueForge agent
```

The gateway sits only between the agent and the LLM. Set `MODEL_PROVIDER=gateway` and bootstrap registers a custom OpenAI-compatible provider `gpt-model/openai`. The upstream model id is `TFY_GATEWAY_MODEL_ID`. `MODEL_PROVIDER=openai` calls OpenAI directly as `openai/janitor-model` (`OPENAI_MODEL_ID`).

## How TrueForge is used

- **UI and agent loop.** Chat, tool calls, and Allow/Deny happen in TrueForge. `scripts/bootstrap_trueforge.py` registers the model provider, the MCP server, the Daytona sandbox, and the agent from `agent/`.
- **Model.** Each LLM call goes out through the configured provider. With the gateway, TrueForge never calls the model host directly.
- **Tools.** TrueForge calls our MCP server. The model only chooses the next tool. The tool's code decides junk, blast radius, and tag refusal.
- **Sandbox.** After the lists and prices are in, the agent writes a Python script. TrueForge runs that script on Daytona and the script writes `teardown-plan.md` and `teardown-plan.csv`. Deletes do not run in the sandbox.
- **Human checkpoint.** Destructive tools raise `tool.approval_required`. In TrueForge's UI you Allow or Deny on the card. The optional dashboard posts the same decision to the API bridge.

## Real vs mocked

| Real | Mocked / simulated |
|---|---|
| AWS resources created by `scripts/seed_aws.py` | Unit tests use moto, not a live account |
| MCP calls against that account during a demo | Prices are a static us-east-1 table, not Cost Explorer |
| The Daytona script and the plan files | "Idle" is a state rule, not 14-day CloudWatch usage |
| Approved deletes | `JANITOR_SNAPSHOT_MIN_AGE_DAYS=0` in the demo so a fresh snapshot is listed |
| Model calls through the gateway (or OpenAI, if selected) | EC2 `DryRun` checks permission; it is not the delete |

## Known limits

- One region and one account per run.
- Other regions reuse the us-east-1 price table. Snapshot price is the full volume size, an upper bound.
- The API audit log is in memory.
- Deletes touch `janitor-demo=true` resources. Clearing `JANITOR_REQUIRE_TAG` is a deliberate choice.
- The MCP server binds to `127.0.0.1` and has no auth of its own. The tag rails still apply.

## Run it

Prerequisites: Node ≥ 22.14, Python ≥ 3.11, an AWS account with a default VPC, a Daytona key with `write:sandboxes`, `write:snapshots`, and `delete:snapshots`, and either a TrueFoundry gateway key (`MODEL_PROVIDER=gateway`) or an OpenAI key (`MODEL_PROVIDER=openai`).

Four processes stay running. Bootstrap and seed run once and exit.

```powershell
cd "C:\Users\Harsh Kumar\OneDrive\Documents\True_Foundry_Hackathon"
copy .env.example .env
# fill keys in .env — never commit .env

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Once per account, with admin credentials (the `cost-janitor` user cannot create IAM roles):

```powershell
aws iam create-service-linked-role --aws-service-name elasticloadbalancing.amazonaws.com
aws iam create-user --user-name cost-janitor
aws iam put-user-policy --user-name cost-janitor --policy-name cloud-cost-janitor --policy-document file://scripts/iam-policy.json
aws iam create-access-key --user-name cost-janitor
```

Terminal 1 — TrueForge. Leave it open.

```powershell
$env:OUTBOUND_URL_ALLOWED_HOSTS='["localhost","127.0.0.1"]'
npx @truefoundry/trueforge@0.2.1
```

Terminal 2 — MCP server. Leave it open.

```powershell
.\.venv\Scripts\Activate.ps1
python -m mcp_server.server
```

Terminal 3 — register the agent, then create demo waste. Both commands exit when they finish.

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.bootstrap_trueforge
python -m scripts.seed_aws
```

Open `http://localhost:8790`, choose the agent `cloud-cost-janitor`, and ask it to clean up `us-east-1`. Approve some deletes and deny one. Afterwards:

```powershell
python -m scripts.cleanup_aws
```

Optional dashboard, two more terminals:

```powershell
uvicorn api.main:app --port 8080
cd web; npm install; npm run dev
```

Then use `http://localhost:5173` and click **Run janitor**. Tests without AWS: `pytest` and `cd web; npm test`.

## Next steps

Multi-region fan-out, Cost Explorer prices, weekly runs via TrueForge Schedules, Slack approvals.
