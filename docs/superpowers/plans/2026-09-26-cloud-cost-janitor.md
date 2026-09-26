# Cloud Cost Janitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An AI agent, running on TrueForge, that finds idle AWS resources, prices them, writes a teardown plan in a sandbox, and deletes only what a human approves — with our own React dashboard driving it.

**Architecture:** TrueForge (`npx @truefoundry/trueforge`, :8790) is the agent engine: OpenAI model, Daytona sandbox, approval gates. Our FastMCP server (:8000/mcp) exposes AWS via boto3 as annotated MCP tools. Our FastAPI bridge (:8080) drives TrueForge through `trueforge-sdk` and relays normalized events over SSE to our React + Vite + Tailwind UI (:5173).

**Tech Stack:** Python 3.12, boto3, `mcp` (FastMCP), FastAPI, sse-starlette, httpx, `trueforge-sdk`, pytest + moto 5 · Node 22.14+, React 18, Vite, Tailwind v4, react-markdown, vitest.

**Spec:** `docs/superpowers/specs/2026-09-26-cloud-cost-janitor-design.md`

## Global Constraints

- Build window: 12:00–19:00 IST, 26 Sep 2026. Submissions close 19:00. Cut scope, never the approval demo.
- **Cut line — 15:30:** if the React app is not integrated end to end by 15:30, stop Tasks 10–11 and demo entirely in TrueForge's UI (http://localhost:8790): scan → sandbox plan file → approve one delete → deny one. The dashboard is polish; the gate is the score. Tasks 1–7 and 12 are never cut.
- Recorded video ≤ 3:00, with ≥ 30 s showing TrueForge itself (its UI at :8790 with the agent and the approval pause). Live demo ≤ 5:00.
- Submission needs an open license (`LICENSE`, MIT) and a writeup in the README: problem, what the agent reaches, where it stops, architecture, how TrueForge is used, real vs mocked, known limits.
- This plan is the source of truth where it differs from the spec.
- Agent MUST run on TrueForge; deletes MUST pause for human approval; generated code MUST run in the TrueForge sandbox.
- AWS credentials live only in the MCP server's environment. Never commit `.env`. Commit `.env.example`.
- Destructive tools refuse any resource lacking tag `janitor-demo=true` (env `JANITOR_REQUIRE_TAG`, empty disables).
- TrueForge resource names match `^[a-z][a-z0-9-]{0,62}[a-z0-9]$` (so the model is registered as `janitor-model`, FQN `openai/janitor-model`; the real OpenAI id goes in `model_id`).
- Ports: TrueForge 8790, MCP 8000 (path `/mcp`), API 8080, web 5173.
- Default region `us-east-1`.
- README must disclose AI assistants used (Claude Code).
- Commit after every task. Do not push until the team agrees (remote: `harshathghara/TrueFoundry_Hackathon`).

## Team split & timeline

| Time | A (AWS/MCP) | B (API/bridge) | C (Web) | D (Setup/demo) |
|---|---|---|---|---|
| 12:00 | Task 1 | Task 1 pair → Task 8 | Task 10 | Task 0 |
| 13:00 | Task 2, 3 | Task 8 | Task 10 | Task 7 |
| 14:00 | Task 4, 5 | Task 9 | Task 11 | Task 7 bootstrap live |
| 15:30 | Task 6 (seed live) | Task 9 live | Task 11 — **cut-line check** | Task 12 |
| 16:00 | — Integration: Task 13 end-to-end (mentor checkpoint) — | | | |
| 17:30 | Bug fixes | Bug fixes | Polish | Record backup video |
| 18:30 | Freeze. Push. Submit. | | | |

## Integration risks (green unit tests can still fail live)

| Risk | Action |
|---|---|
| Bootstrap bodies are inferred from docs | On the first live run (Task 7.6), compare any 400 with http://localhost:8790/api/v1/docs **before** UI work. |
| Event shapes in Task 8 are assumed | After the TrueForge smoke test, capture a real stream (Task 9.9 `JANITOR_DUMP_EVENTS`) and lock `test_real_stream_fixture` to it. |
| Approvals may pause one tool at a time | The UI submits whatever cards are pending, so per-call pauses just mean one card per round. Demo still works. |
| No default VPC in credits account | Task 0 Step 3b checks it before 16:00. ALB + stop waiters take a few minutes. |
| ELB ignores `aws:ResourceTag` in IAM | If an approved ALB delete returns AccessDenied, switch that action's condition key to `elasticloadbalancing:ResourceTag/janitor-demo`. Never drop the tag check. |
| `trueforge-sdk` doesn't resolve on PyPI | Pin whatever `pip index versions trueforge-sdk` lists. Bootstrap uses plain HTTP; only the bridge needs the SDK. |
| Shell differences | Git Bash: `source .venv/Scripts/activate`. PowerShell: `.venv\Scripts\Activate.ps1`. |

## File Structure

```
TrueFoundry_Hackathon/
├── requirements.txt, requirements-dev.txt, pytest.ini, .env.example, .gitignore, README.md (writeup), LICENSE (MIT)
├── mcp_server/
│   ├── __init__.py
│   ├── pricing.py        # static price table + monthly_cost/estimate (pure)
│   ├── aws_scan.py       # list_* discovery functions (boto3, read-only)
│   ├── aws_blast.py      # check_blast_radius (read-only)
│   ├── aws_actions.py    # tag rail, dry-run, snapshot + destructive actions
│   └── server.py         # FastMCP wiring, annotations, error wrapping, entrypoint
├── api/
│   ├── __init__.py
│   ├── events.py         # Normalizer: TrueForge event dicts -> UI events (pure)
│   ├── runner.py         # SessionRunner: SDK stream in a thread, buffer, subscribers, decisions, audit
│   └── main.py           # FastAPI app: /api/scan, /events (SSE), /decisions, /audit, /health
├── agent/
│   ├── instructions.md   # system prompt
│   └── manifest.py       # build_agent_manifest()
├── scripts/
│   ├── __init__.py
│   ├── bootstrap_trueforge.py  # upsert model provider, MCP server, sandbox, agent
│   ├── seed_aws.py             # create tagged demo waste
│   ├── cleanup_aws.py          # delete all tagged demo resources
│   └── iam-policy.json
├── tests/
│   ├── conftest.py
│   ├── test_pricing.py, test_aws_scan.py, test_aws_blast.py, test_aws_actions.py, test_server.py
│   ├── test_seed_cleanup.py, test_bootstrap.py, test_events.py, test_runner.py, test_main.py
│   └── fixtures/real_turn.jsonl   # captured live TrueForge stream (Task 9 Step 10)
└── web/                  # Vite React TS app
    ├── vite.config.ts
    └── src/{main.tsx, App.tsx, index.css, types.ts, state.ts, state.test.ts, api.ts, useSession.ts,
             components/{KpiStrip,ScanPanel,AgentFeed,ResourceTable,ApprovalCards,PlanView,AuditTrail}.tsx}
```

---

### Task 0: Accounts & runtime (D, manual, parallel with Task 1)

**Files:** none (produces `.env` values)

- [ ] **Step 1: Daytona key.** Sign up at daytona.io → API Keys → create a key with **Sandboxes** access AND **Snapshots write (create)**. (Without snapshot permission TrueForge sandbox setup fails.)
- [ ] **Step 2: OpenAI key** from the organisers. Pick the model id they grant (e.g. `gpt-5.2`); record as `OPENAI_MODEL_ID`.
- [ ] **Step 3: AWS IAM user** `cost-janitor` in the credits account. Attach the policy from Task 6's `scripts/iam-policy.json` (until it exists, use `ReadOnlyAccess` + the Task 6 policy later). Create an access key.
- [ ] **Step 3b: Default VPC check** (seed needs a default VPC with ≥ 2 subnets in different AZs).

Run: `aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[].VpcId" --region us-east-1`
Expected: one `vpc-…` id. If empty: `aws ec2 create-default-vpc --region us-east-1`.

- [ ] **Step 4: Start TrueForge.**

Run: `node -v` (must be ≥ 22.14) then `npx @truefoundry/trueforge@latest`
Expected: server on `http://localhost:8790`; opening it shows the chat UI; `curl http://localhost:8790/api/v1/agents` returns JSON.

- [ ] **Step 5:** Put all values in `TrueFoundry_Hackathon/.env` (template in Task 1). Share with teammates out-of-band, never in git.

---

### Task 1: Repo scaffold + pricing (A with B)

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.env.example`, `.gitignore` (overwrite), `mcp_server/__init__.py`, `mcp_server/pricing.py`, `tests/conftest.py`, `tests/test_pricing.py`

**Interfaces:**
- Produces: `mcp_server.pricing.monthly_cost(resource: dict, region: str) -> float`, `mcp_server.pricing.estimate(resources: list[dict], region: str) -> dict` returning `{"region", "items": [resource + "monthly_cost"], "total_monthly_cost": float}`. Resource dicts use `kind` ∈ `ebs | snapshot | eip | lb | ec2_stopped`.

- [ ] **Step 1: Scaffold files**

`requirements.txt`:
```
boto3>=1.35
mcp[cli]>=1.12
fastapi>=0.115
uvicorn[standard]>=0.30
sse-starlette>=2.1
httpx>=0.27
python-dotenv>=1.0
trueforge-sdk
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8
moto[ec2,elbv2,route53]>=5.0
```

`pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

`.env.example`:
```
# OpenAI (given by organisers)
OPENAI_API_KEY=
OPENAI_MODEL_ID=gpt-5.2
# Daytona sandbox (needs Sandboxes + Snapshots write)
DAYTONA_API_KEY=
# AWS (IAM user cost-janitor) — read by the MCP server only
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
# Safety rail: destructive tools only touch resources with this tag (empty = disabled)
JANITOR_REQUIRE_TAG=janitor-demo=true
# Snapshots younger than this are ignored (0 for the live demo, 30 in real life)
JANITOR_SNAPSHOT_MIN_AGE_DAYS=0
# Wiring
TRUEFORGE_BASE_URL=http://localhost:8790
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PUBLIC_URL=http://localhost:8000/mcp
AGENT_NAME=cloud-cost-janitor
```

`.gitignore`:
```
.env
.env.*
!.env.example
.venv/
__pycache__/
*.pyc
.pytest_cache/
node_modules/
web/dist/
```

`mcp_server/__init__.py`: empty file.

`tests/conftest.py`:
```python
import os

import boto3
import pytest
from moto import mock_aws

os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "JANITOR_REQUIRE_TAG": "janitor-demo=true",
    }
)

REGION = "us-east-1"
DEMO_TAG = {"Key": "janitor-demo", "Value": "true"}


@pytest.fixture
def aws():
    with mock_aws():
        yield


@pytest.fixture
def ec2(aws):
    return boto3.client("ec2", region_name=REGION)


@pytest.fixture
def elbv2(aws):
    return boto3.client("elbv2", region_name=REGION)


@pytest.fixture
def ami_id(ec2):
    return ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]


@pytest.fixture
def az(ec2):
    return ec2.describe_availability_zones()["AvailabilityZones"][0]["ZoneName"]
```

- [ ] **Step 2: Create venv and install**

Run (Git Bash): `python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements-dev.txt`
Expected: installs without error. (If `trueforge-sdk` fails to resolve, run `pip index versions trueforge-sdk` and pin the listed version.)

- [ ] **Step 3: Write the failing test** `tests/test_pricing.py`:
```python
import pytest

from mcp_server.pricing import estimate, monthly_cost


def test_ebs_gp3_priced_per_gb():
    assert monthly_cost({"kind": "ebs", "size_gb": 100, "volume_type": "gp3"}, "us-east-1") == 8.0


def test_unknown_volume_type_falls_back_to_gp3():
    assert monthly_cost({"kind": "ebs", "size_gb": 10, "volume_type": "weird"}, "us-east-1") == 0.8


def test_stopped_instance_costs_its_volumes():
    r = {"kind": "ec2_stopped", "volumes": [{"kind": "ebs", "size_gb": 8, "volume_type": "gp2"}]}
    assert monthly_cost(r, "us-east-1") == 0.8


def test_eip_lb_snapshot():
    assert monthly_cost({"kind": "eip"}, "us-east-1") == 3.6
    assert monthly_cost({"kind": "lb", "lb_type": "application"}, "us-east-1") == 16.43
    assert monthly_cost({"kind": "snapshot", "size_gb": 20}, "us-east-1") == 1.0


def test_unknown_region_uses_default_prices():
    assert monthly_cost({"kind": "eip"}, "ap-south-1") == 3.6


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        monthly_cost({"kind": "rds"}, "us-east-1")


def test_estimate_totals_and_annotates():
    out = estimate([{"id": "a", "kind": "eip"}, {"id": "b", "kind": "ebs", "size_gb": 10, "volume_type": "gp3"}], "us-east-1")
    assert out["total_monthly_cost"] == 4.4
    assert [i["monthly_cost"] for i in out["items"]] == [3.6, 0.8]
    assert out["items"][0]["id"] == "a"
```

- [ ] **Step 4: Run to verify it fails**

Run: `pytest tests/test_pricing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.pricing'`

- [ ] **Step 5: Implement** `mcp_server/pricing.py`:
```python
"""Static AWS list prices (USD/month) used for demo cost estimates.

Cost Explorer lags ~24h and has no history for freshly created resources, so we price from a table.
"""

DEFAULT_REGION = "us-east-1"

PRICES = {
    "us-east-1": {
        "ebs_gb": {"gp3": 0.08, "gp2": 0.10, "io1": 0.125, "io2": 0.125, "st1": 0.045, "sc1": 0.015, "standard": 0.05},
        "snapshot_gb": 0.05,
        "eip": 3.60,
        "alb": 16.43,
        "nlb": 16.43,
    },
}


def _prices(region: str) -> dict:
    return PRICES.get(region, PRICES[DEFAULT_REGION])


def monthly_cost(resource: dict, region: str) -> float:
    p = _prices(region)
    kind = resource["kind"]
    if kind == "ebs":
        rate = p["ebs_gb"].get(resource.get("volume_type", "gp3"), p["ebs_gb"]["gp3"])
        return round(resource["size_gb"] * rate, 2)
    if kind == "snapshot":
        # Upper bound: snapshots are incremental, we price the full source volume size.
        return round(resource["size_gb"] * p["snapshot_gb"], 2)
    if kind == "eip":
        return p["eip"]
    if kind == "lb":
        return p["nlb"] if resource.get("lb_type") == "network" else p["alb"]
    if kind == "ec2_stopped":
        # A stopped instance has no compute charge but still pays for its EBS volumes.
        return round(sum(monthly_cost(v, region) for v in resource.get("volumes", [])), 2)
    raise ValueError(f"unknown resource kind: {kind}")


def estimate(resources: list[dict], region: str) -> dict:
    items = [{**r, "monthly_cost": monthly_cost(r, region)} for r in resources]
    return {
        "region": region,
        "items": items,
        "total_monthly_cost": round(sum(i["monthly_cost"] for i in items), 2),
    }
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/test_pricing.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**
```bash
git add requirements.txt requirements-dev.txt pytest.ini .env.example .gitignore mcp_server tests
git commit -m "feat: scaffold repo and static cost pricing"
```

---

### Task 2: AWS discovery tools (A)

**Files:**
- Create: `mcp_server/aws_scan.py`, `tests/test_aws_scan.py`

**Interfaces:**
- Consumes: conftest fixtures `ec2`, `elbv2`, `ami_id`, `az`, `DEMO_TAG`.
- Produces (all `(region: str) -> list[dict]`, each dict has `kind`, `id`, `tags: dict`):
  - `list_unattached_volumes` → `{kind:"ebs", id, size_gb, volume_type, age_days, tags}`
  - `list_stopped_instances` → `{kind:"ec2_stopped", id, instance_type, volumes:[{kind:"ebs", id, size_gb, volume_type}], state_reason, tags}`
  - `list_unassociated_eips` → `{kind:"eip", id(allocation id), public_ip, tags}`
  - `list_idle_load_balancers` → `{kind:"lb", id(arn), name, lb_type, dns_name, tags}`
  - `list_old_snapshots(region, older_than_days: int | None = None)` → `{kind:"snapshot", id, size_gb, age_days, volume_id, tags}`; `None` reads env `JANITOR_SNAPSHOT_MIN_AGE_DAYS` (default 30); excludes snapshots tagged `janitor-backup=true`.
  - helper `tags_of(tag_list) -> dict`

- [ ] **Step 1: Write the failing test** `tests/test_aws_scan.py`:
```python
from conftest import DEMO_TAG, REGION

from mcp_server import aws_scan


def _vol(ec2, az, tags=None, size=8):
    kw = {"AvailabilityZone": az, "Size": size, "VolumeType": "gp3"}
    if tags:
        kw["TagSpecifications"] = [{"ResourceType": "volume", "Tags": tags}]
    return ec2.create_volume(**kw)["VolumeId"]


def test_unattached_volumes_found_with_tags(ec2, az):
    vid = _vol(ec2, az, [DEMO_TAG])
    items = aws_scan.list_unattached_volumes(REGION)
    item = next(i for i in items if i["id"] == vid)
    assert item["kind"] == "ebs" and item["size_gb"] == 8 and item["volume_type"] == "gp3"
    assert item["tags"] == {"janitor-demo": "true"}


def test_attached_volume_not_listed(ec2, az, ami_id):
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1, Placement={"AvailabilityZone": az})["Instances"][0]["InstanceId"]
    vid = _vol(ec2, az)
    ec2.attach_volume(VolumeId=vid, InstanceId=iid, Device="/dev/sdf")
    assert vid not in {i["id"] for i in aws_scan.list_unattached_volumes(REGION)}


def test_stopped_instance_listed_with_volumes(ec2, ami_id):
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1, InstanceType="t3.micro")["Instances"][0]["InstanceId"]
    ec2.stop_instances(InstanceIds=[iid])
    item = next(i for i in aws_scan.list_stopped_instances(REGION) if i["id"] == iid)
    assert item["kind"] == "ec2_stopped" and item["instance_type"] == "t3.micro"
    assert all(v["kind"] == "ebs" for v in item["volumes"])


def test_running_instance_not_listed(ec2, ami_id):
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1)["Instances"][0]["InstanceId"]
    assert iid not in {i["id"] for i in aws_scan.list_stopped_instances(REGION)}


def test_unassociated_eip_listed(ec2):
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    assert alloc in {i["id"] for i in aws_scan.list_unassociated_eips(REGION)}


def test_idle_lb_listed_but_lb_with_target_not(ec2, elbv2, ami_id):
    vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    subnets = [s["SubnetId"] for s in ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]}])["Subnets"]][:2]

    def lb_with_tg(name):
        lb = elbv2.create_load_balancer(Name=name, Subnets=subnets, Type="application")["LoadBalancers"][0]
        tg = elbv2.create_target_group(Name=f"{name}-tg", Protocol="HTTP", Port=80, VpcId=vpc, TargetType="instance")["TargetGroups"][0]
        elbv2.create_listener(LoadBalancerArn=lb["LoadBalancerArn"], Protocol="HTTP", Port=80,
                              DefaultActions=[{"Type": "forward", "TargetGroupArn": tg["TargetGroupArn"]}])
        return lb["LoadBalancerArn"], tg["TargetGroupArn"]

    idle_arn, _ = lb_with_tg("idle")
    busy_arn, busy_tg = lb_with_tg("busy")
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1, SubnetId=subnets[0])["Instances"][0]["InstanceId"]
    elbv2.register_targets(TargetGroupArn=busy_tg, Targets=[{"Id": iid}])

    ids = {i["id"] for i in aws_scan.list_idle_load_balancers(REGION)}
    assert idle_arn in ids and busy_arn not in ids


def test_old_snapshots_respects_age_and_backup_tag(ec2, az):
    vid = _vol(ec2, az)
    snap = ec2.create_snapshot(VolumeId=vid)["SnapshotId"]
    backup = ec2.create_snapshot(VolumeId=vid, TagSpecifications=[{"ResourceType": "snapshot", "Tags": [{"Key": "janitor-backup", "Value": "true"}]}])["SnapshotId"]
    ids0 = {i["id"] for i in aws_scan.list_old_snapshots(REGION, older_than_days=0)}
    assert snap in ids0 and backup not in ids0
    assert snap not in {i["id"] for i in aws_scan.list_old_snapshots(REGION, older_than_days=30)}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_aws_scan.py -v`
Expected: FAIL — `ImportError: cannot import name 'aws_scan'`

- [ ] **Step 3: Implement** `mcp_server/aws_scan.py`:
```python
"""Read-only discovery of idle AWS resources."""
import os
from datetime import datetime, timezone

import boto3


def tags_of(tag_list) -> dict:
    return {t["Key"]: t["Value"] for t in tag_list or []}


def _age_days(dt) -> int:
    return (datetime.now(timezone.utc) - dt).days


def _ec2(region):
    return boto3.client("ec2", region_name=region)


def list_unattached_volumes(region: str) -> list[dict]:
    out = []
    for page in _ec2(region).get_paginator("describe_volumes").paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
        for v in page["Volumes"]:
            out.append({"kind": "ebs", "id": v["VolumeId"], "size_gb": v["Size"], "volume_type": v["VolumeType"],
                        "age_days": _age_days(v["CreateTime"]), "tags": tags_of(v.get("Tags"))})
    return out


def list_stopped_instances(region: str) -> list[dict]:
    ec2 = _ec2(region)
    out = []
    for page in ec2.get_paginator("describe_instances").paginate(Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]):
        for res in page["Reservations"]:
            for inst in res["Instances"]:
                vol_ids = [m["Ebs"]["VolumeId"] for m in inst.get("BlockDeviceMappings", []) if "Ebs" in m]
                vols = ec2.describe_volumes(VolumeIds=vol_ids)["Volumes"] if vol_ids else []
                out.append({
                    "kind": "ec2_stopped", "id": inst["InstanceId"], "instance_type": inst["InstanceType"],
                    "volumes": [{"kind": "ebs", "id": v["VolumeId"], "size_gb": v["Size"], "volume_type": v["VolumeType"]} for v in vols],
                    "state_reason": inst.get("StateTransitionReason", ""), "tags": tags_of(inst.get("Tags")),
                })
    return out


def list_unassociated_eips(region: str) -> list[dict]:
    return [
        {"kind": "eip", "id": a["AllocationId"], "public_ip": a.get("PublicIp"), "tags": tags_of(a.get("Tags"))}
        for a in _ec2(region).describe_addresses()["Addresses"]
        if "AssociationId" not in a and "AllocationId" in a
    ]


def list_idle_load_balancers(region: str) -> list[dict]:
    elb = boto3.client("elbv2", region_name=region)
    out = []
    for page in elb.get_paginator("describe_load_balancers").paginate():
        for lb in page["LoadBalancers"]:
            arn = lb["LoadBalancerArn"]
            tgs = elb.describe_target_groups(LoadBalancerArn=arn)["TargetGroups"]
            targets = sum(len(elb.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])["TargetHealthDescriptions"]) for tg in tgs)
            if targets:
                continue
            tag_desc = elb.describe_tags(ResourceArns=[arn])["TagDescriptions"]
            out.append({"kind": "lb", "id": arn, "name": lb["LoadBalancerName"], "lb_type": lb["Type"],
                        "dns_name": lb["DNSName"], "tags": tags_of(tag_desc[0]["Tags"] if tag_desc else [])})
    return out


def list_old_snapshots(region: str, older_than_days: int | None = None) -> list[dict]:
    if older_than_days is None:
        older_than_days = int(os.getenv("JANITOR_SNAPSHOT_MIN_AGE_DAYS", "30"))
    out = []
    for page in _ec2(region).get_paginator("describe_snapshots").paginate(OwnerIds=["self"]):
        for s in page["Snapshots"]:
            tags = tags_of(s.get("Tags"))
            if tags.get("janitor-backup") == "true" or _age_days(s["StartTime"]) < older_than_days:
                continue
            out.append({"kind": "snapshot", "id": s["SnapshotId"], "size_gb": s["VolumeSize"],
                        "age_days": _age_days(s["StartTime"]), "volume_id": s.get("VolumeId"), "tags": tags})
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_aws_scan.py -v`
Expected: 7 passed. (If moto rejects `Type="application"` without a security group, add `SecurityGroups=[]`—do not change production code for it.)

- [ ] **Step 5: Commit**
```bash
git add mcp_server/aws_scan.py tests/test_aws_scan.py
git commit -m "feat: add read-only AWS idle-resource discovery"
```

---

### Task 3: Blast radius check (A)

**Files:**
- Create: `mcp_server/aws_blast.py`, `tests/test_aws_blast.py`

**Interfaces:**
- Consumes: `aws_scan.tags_of`.
- Produces: `check_blast_radius(resource_id: str, region: str) -> dict` = `{"resource_id", "safe": bool, "reasons": list[str], "warnings": list[str]}`. Pure helpers `snapshots_used_by_amis(images: list[dict]) -> dict[str, str]` (snapshot id → AMI id) and `records_aliasing(dns_name: str, records: list[dict]) -> list[str]`.

- [ ] **Step 1: Write the failing test** `tests/test_aws_blast.py`:
```python
from conftest import DEMO_TAG, REGION

from mcp_server.aws_blast import check_blast_radius, records_aliasing, snapshots_used_by_amis


def test_snapshots_used_by_amis():
    images = [{"ImageId": "ami-1", "BlockDeviceMappings": [{"Ebs": {"SnapshotId": "snap-a"}}, {"DeviceName": "x"}]}]
    assert snapshots_used_by_amis(images) == {"snap-a": "ami-1"}


def test_records_aliasing_matches_case_and_trailing_dot():
    records = [{"Name": "api.example.com.", "AliasTarget": {"DNSName": "dualstack.My-LB-1.us-east-1.elb.amazonaws.com."}},
               {"Name": "www.example.com.", "Type": "A"}]
    assert records_aliasing("my-lb-1.us-east-1.elb.amazonaws.com", records) == ["api.example.com."]


def test_unattached_demo_volume_is_safe(ec2, az):
    vid = ec2.create_volume(AvailabilityZone=az, Size=8, TagSpecifications=[{"ResourceType": "volume", "Tags": [DEMO_TAG]}])["VolumeId"]
    out = check_blast_radius(vid, REGION)
    assert out == {"resource_id": vid, "safe": True, "reasons": [], "warnings": []}


def test_prod_tag_is_unsafe(ec2, az):
    vid = ec2.create_volume(AvailabilityZone=az, Size=8, TagSpecifications=[{"ResourceType": "volume", "Tags": [{"Key": "env", "Value": "prod"}]}])["VolumeId"]
    out = check_blast_radius(vid, REGION)
    assert out["safe"] is False and any("env=prod" in r for r in out["reasons"])


def test_termination_protected_instance_is_unsafe(ec2, ami_id):
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1, DisableApiTermination=True)["Instances"][0]["InstanceId"]
    out = check_blast_radius(iid, REGION)
    assert out["safe"] is False and any("termination protection" in r for r in out["reasons"])


def test_unknown_prefix_is_unsafe():
    out = check_blast_radius("db-xyz", REGION)
    assert out["safe"] is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_aws_blast.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.aws_blast'`

- [ ] **Step 3: Implement** `mcp_server/aws_blast.py`:
```python
"""Dependency checks run before proposing any deletion."""
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from mcp_server.aws_scan import tags_of


def snapshots_used_by_amis(images: list[dict]) -> dict[str, str]:
    used = {}
    for img in images:
        for m in img.get("BlockDeviceMappings", []):
            snap = m.get("Ebs", {}).get("SnapshotId")
            if snap:
                used[snap] = img["ImageId"]
    return used


def _norm_dns(name: str) -> str:
    name = name.lower().rstrip(".")
    return name[len("dualstack."):] if name.startswith("dualstack.") else name


def records_aliasing(dns_name: str, records: list[dict]) -> list[str]:
    target = _norm_dns(dns_name)
    return [r["Name"] for r in records if "AliasTarget" in r and _norm_dns(r["AliasTarget"]["DNSName"]) == target]


def _prod_reason(tags: dict) -> list[str]:
    return ["tagged env=prod"] if tags.get("env", "").lower() in {"prod", "production"} else []


def _volume(ec2, vid):
    v = ec2.describe_volumes(VolumeIds=[vid])["Volumes"][0]
    reasons = _prod_reason(tags_of(v.get("Tags")))
    reasons += [f"attached to {a['InstanceId']}" for a in v.get("Attachments", [])]
    return reasons, []


def _snapshot(ec2, sid):
    s = ec2.describe_snapshots(SnapshotIds=[sid])["Snapshots"][0]
    reasons = _prod_reason(tags_of(s.get("Tags")))
    ami = snapshots_used_by_amis(ec2.describe_images(Owners=["self"])["Images"]).get(sid)
    if ami:
        reasons.append(f"backs AMI {ami}")
    return reasons, []


def _instance(ec2, iid):
    inst = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]
    reasons = _prod_reason(tags_of(inst.get("Tags")))
    if ec2.describe_instance_attribute(InstanceId=iid, Attribute="disableApiTermination")["DisableApiTermination"]["Value"]:
        reasons.append("termination protection enabled")
    return reasons, []


def _eip(ec2, alloc):
    a = ec2.describe_addresses(AllocationIds=[alloc])["Addresses"][0]
    reasons = _prod_reason(tags_of(a.get("Tags")))
    if a.get("AssociationId"):
        reasons.append(f"associated with {a.get('InstanceId') or a.get('NetworkInterfaceId')}")
    return reasons, []


def _load_balancer(region, arn):
    elb = boto3.client("elbv2", region_name=region)
    lb = elb.describe_load_balancers(LoadBalancerArns=[arn])["LoadBalancers"][0]
    reasons = _prod_reason(tags_of(elb.describe_tags(ResourceArns=[arn])["TagDescriptions"][0]["Tags"]))
    warnings = []
    try:
        r53 = boto3.client("route53")
        for zone in r53.list_hosted_zones()["HostedZones"]:
            records = r53.list_resource_record_sets(HostedZoneId=zone["Id"])["ResourceRecordSets"]
            reasons += [f"DNS record {n} points here" for n in records_aliasing(lb["DNSName"], records)]
    except (ClientError, BotoCoreError) as e:
        warnings.append(f"could not check Route 53: {e}")
    return reasons, warnings


def check_blast_radius(resource_id: str, region: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    if resource_id.startswith("vol-"):
        reasons, warnings = _volume(ec2, resource_id)
    elif resource_id.startswith("snap-"):
        reasons, warnings = _snapshot(ec2, resource_id)
    elif resource_id.startswith("i-"):
        reasons, warnings = _instance(ec2, resource_id)
    elif resource_id.startswith("eipalloc-"):
        reasons, warnings = _eip(ec2, resource_id)
    elif resource_id.startswith("arn:") and ":loadbalancer/" in resource_id:
        reasons, warnings = _load_balancer(region, resource_id)
    else:
        reasons, warnings = [f"unsupported resource id: {resource_id}"], []
    return {"resource_id": resource_id, "safe": not reasons, "reasons": reasons, "warnings": warnings}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_aws_blast.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**
```bash
git add mcp_server/aws_blast.py tests/test_aws_blast.py
git commit -m "feat: add blast-radius checks for cleanup candidates"
```

---

### Task 4: Actions with tag rail and dry-run (A)

**Files:**
- Create: `mcp_server/aws_actions.py`, `tests/test_aws_actions.py`

**Interfaces:**
- Consumes: `aws_scan.tags_of`.
- Produces (all return `{"ok": bool, "action": str, "resource_id": str, "error"?: str, ...}`):
  `snapshot_volume(volume_id, region)` (adds `snapshot_id`), `delete_volume(volume_id, region)`, `terminate_instance(instance_id, region)`, `release_eip(allocation_id, region)`, `delete_snapshot(snapshot_id, region)`, `delete_load_balancer(arn, region)`. Backup snapshots are tagged `janitor-backup=true` and `janitor-demo=true`.
- Rails (all six tools, including `snapshot_volume`): refuse `env=prod|production` **always**; refuse resources missing `JANITOR_REQUIRE_TAG` unless that env is empty. IAM limits deletes to the demo tag; the prod refusal is this second, in-tool check — IAM does not block prod.

- [ ] **Step 1: Write the failing test** `tests/test_aws_actions.py`:
```python
import pytest
from conftest import DEMO_TAG, REGION

from mcp_server import aws_actions


def _vol(ec2, az, tags):
    kw = {"AvailabilityZone": az, "Size": 8}
    if tags:
        kw["TagSpecifications"] = [{"ResourceType": "volume", "Tags": tags}]
    return ec2.create_volume(**kw)["VolumeId"]


def test_delete_volume_refuses_untagged(ec2, az):
    vid = _vol(ec2, az, None)
    out = aws_actions.delete_volume(vid, REGION)
    assert out["ok"] is False and "janitor-demo=true" in out["error"]
    assert ec2.describe_volumes(VolumeIds=[vid])["Volumes"]


def test_delete_volume_deletes_tagged(ec2, az):
    vid = _vol(ec2, az, [DEMO_TAG])
    out = aws_actions.delete_volume(vid, REGION)
    assert out == {"ok": True, "action": "delete_volume", "resource_id": vid}
    assert vid not in {v["VolumeId"] for v in ec2.describe_volumes()["Volumes"]}


def test_tag_rail_can_be_disabled(ec2, az, monkeypatch):
    monkeypatch.setenv("JANITOR_REQUIRE_TAG", "")
    vid = _vol(ec2, az, None)
    assert aws_actions.delete_volume(vid, REGION)["ok"] is True


def test_prod_decoy_refused_even_with_demo_tag(ec2, az, monkeypatch):
    vid = _vol(ec2, az, [DEMO_TAG, {"Key": "env", "Value": "prod"}])
    for fn in (aws_actions.delete_volume, aws_actions.snapshot_volume):
        out = fn(vid, REGION)
        assert out["ok"] is False and "env=prod" in out["error"]
    monkeypatch.setenv("JANITOR_REQUIRE_TAG", "")  # prod refusal does not depend on the demo-tag rail
    assert "env=prod" in aws_actions.delete_volume(vid, REGION)["error"]
    assert ec2.describe_volumes(VolumeIds=[vid])["Volumes"]


def test_snapshot_refuses_untagged(ec2, az):
    vid = _vol(ec2, az, None)
    out = aws_actions.snapshot_volume(vid, REGION)
    assert out["ok"] is False and "janitor-demo=true" in out["error"]


def test_snapshot_volume_tags_backup(ec2, az):
    vid = _vol(ec2, az, [DEMO_TAG])
    out = aws_actions.snapshot_volume(vid, REGION)
    assert out["ok"] is True
    snap = ec2.describe_snapshots(SnapshotIds=[out["snapshot_id"]])["Snapshots"][0]
    assert {"Key": "janitor-backup", "Value": "true"} in snap["Tags"]


def test_terminate_and_release_and_delete_snapshot(ec2, az, ami_id):
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1,
                            TagSpecifications=[{"ResourceType": "instance", "Tags": [DEMO_TAG]}])["Instances"][0]["InstanceId"]
    assert aws_actions.terminate_instance(iid, REGION)["ok"] is True

    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.create_tags(Resources=[alloc], Tags=[DEMO_TAG])
    assert aws_actions.release_eip(alloc, REGION)["ok"] is True

    vid = _vol(ec2, az, None)
    snap = ec2.create_snapshot(VolumeId=vid, TagSpecifications=[{"ResourceType": "snapshot", "Tags": [DEMO_TAG]}])["SnapshotId"]
    assert aws_actions.delete_snapshot(snap, REGION)["ok"] is True


def test_missing_resource_returns_error_not_exception(ec2):
    out = aws_actions.delete_volume("vol-0000000000000000", REGION)
    assert out["ok"] is False and out["error"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_aws_actions.py -v`
Expected: FAIL — `ImportError: cannot import name 'aws_actions'`

- [ ] **Step 3: Implement** `mcp_server/aws_actions.py`:
```python
"""State-changing AWS actions. Destructive ones enforce a tag rail and an EC2 dry-run first."""
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from mcp_server.aws_scan import tags_of


def _result(action, resource_id, error=None, **extra):
    out = {"ok": error is None, "action": action, "resource_id": resource_id, **extra}
    if error:
        out["error"] = error
    return out


PROD_VALUES = {"prod", "production"}


def _tag_violation(tags: dict) -> str | None:
    # Always on, independent of JANITOR_REQUIRE_TAG and of IAM: the tool itself never touches prod.
    if tags.get("env", "").lower() in PROD_VALUES:
        return "refused: resource is tagged env=prod"
    required = os.getenv("JANITOR_REQUIRE_TAG", "janitor-demo=true").strip()
    if not required:
        return None
    key, _, value = required.partition("=")
    if tags.get(key) != value:
        return f"refused: resource is not tagged {required}"
    return None


def _dry_run(fn, **kwargs) -> str | None:
    try:
        fn(DryRun=True, **kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] == "DryRunOperation":
            return None
        return f"dry-run failed: {e.response['Error']['Code']}: {e.response['Error'].get('Message', '')}"
    return None


def _guarded(action, resource_id, get_tags, do, dry_run=None):
    try:
        violation = _tag_violation(get_tags())
        if violation:
            return _result(action, resource_id, violation)
        if dry_run:
            err = dry_run()
            if err:
                return _result(action, resource_id, err)
        do()
        return _result(action, resource_id)
    except (ClientError, BotoCoreError, IndexError) as e:
        return _result(action, resource_id, f"{type(e).__name__}: {e}")


def snapshot_volume(volume_id: str, region: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    try:
        violation = _tag_violation(tags_of(ec2.describe_volumes(VolumeIds=[volume_id])["Volumes"][0].get("Tags")))
        if violation:
            return _result("snapshot_volume", volume_id, violation)
        snap = ec2.create_snapshot(
            VolumeId=volume_id,
            Description=f"cloud-cost-janitor backup of {volume_id}",
            TagSpecifications=[{"ResourceType": "snapshot", "Tags": [
                {"Key": "janitor-backup", "Value": "true"}, {"Key": "janitor-demo", "Value": "true"}]}],
        )
        return _result("snapshot_volume", volume_id, snapshot_id=snap["SnapshotId"])
    except (ClientError, BotoCoreError, IndexError) as e:
        return _result("snapshot_volume", volume_id, f"{type(e).__name__}: {e}")


def delete_volume(volume_id: str, region: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    return _guarded(
        "delete_volume", volume_id,
        lambda: tags_of(ec2.describe_volumes(VolumeIds=[volume_id])["Volumes"][0].get("Tags")),
        lambda: ec2.delete_volume(VolumeId=volume_id),
        lambda: _dry_run(ec2.delete_volume, VolumeId=volume_id),
    )


def terminate_instance(instance_id: str, region: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    return _guarded(
        "terminate_instance", instance_id,
        lambda: tags_of(ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0].get("Tags")),
        lambda: ec2.terminate_instances(InstanceIds=[instance_id]),
        lambda: _dry_run(ec2.terminate_instances, InstanceIds=[instance_id]),
    )


def release_eip(allocation_id: str, region: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    return _guarded(
        "release_eip", allocation_id,
        lambda: tags_of(ec2.describe_addresses(AllocationIds=[allocation_id])["Addresses"][0].get("Tags")),
        lambda: ec2.release_address(AllocationId=allocation_id),
        lambda: _dry_run(ec2.release_address, AllocationId=allocation_id),
    )


def delete_snapshot(snapshot_id: str, region: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    return _guarded(
        "delete_snapshot", snapshot_id,
        lambda: tags_of(ec2.describe_snapshots(SnapshotIds=[snapshot_id])["Snapshots"][0].get("Tags")),
        lambda: ec2.delete_snapshot(SnapshotId=snapshot_id),
        lambda: _dry_run(ec2.delete_snapshot, SnapshotId=snapshot_id),
    )


def delete_load_balancer(arn: str, region: str) -> dict:
    elb = boto3.client("elbv2", region_name=region)  # elbv2 has no DryRun
    return _guarded(
        "delete_load_balancer", arn,
        lambda: tags_of(elb.describe_tags(ResourceArns=[arn])["TagDescriptions"][0]["Tags"]),
        lambda: elb.delete_load_balancer(LoadBalancerArn=arn),
    )
```
Note: `_tag_violation` reads the env on every call so `monkeypatch.setenv` works.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_aws_actions.py -v`
Expected: 8 passed. If `test_delete_volume_deletes_tagged` fails because the volume is gone before the real delete, moto ignored `DryRun` — confirm with `pytest -x -vv`; then check moto version ≥ 5.0.

- [ ] **Step 5: Commit**
```bash
git add mcp_server/aws_actions.py tests/test_aws_actions.py
git commit -m "feat: add guarded AWS cleanup actions with tag rail and dry-run"
```

---

### Task 5: FastMCP server (A)

**Files:**
- Create: `mcp_server/server.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `pricing.estimate`, all `aws_scan.list_*`, `aws_blast.check_blast_radius`, all `aws_actions.*`.
- Produces: MCP tools named exactly: `list_unattached_volumes`, `list_stopped_instances`, `list_idle_load_balancers`, `list_unassociated_eips`, `list_old_snapshots`, `estimate_monthly_cost`, `check_blast_radius`, `snapshot_volume`, `delete_volume`, `terminate_instance`, `delete_load_balancer`, `release_eip`, `delete_snapshot`. List tools return `{"region", "items"}`. Module-level `DESTRUCTIVE_TOOLS: list[str]` used by Task 7. Run: `python -m mcp_server.server` → `http://MCP_HOST:MCP_PORT/mcp`.

- [ ] **Step 1: Write the failing test** `tests/test_server.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — `ImportError: cannot import name 'server'`

- [ ] **Step 3: Implement** `mcp_server/server.py`:
```python
"""aws-janitor MCP server: exposes AWS cleanup as annotated MCP tools over streamable HTTP."""
import functools
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_server import aws_actions, aws_blast, aws_scan, pricing

load_dotenv()

DEFAULT_REGION = os.getenv("AWS_REGION", "us-east-1")
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

READ_TOOLS = ["list_unattached_volumes", "list_stopped_instances", "list_idle_load_balancers",
              "list_unassociated_eips", "list_old_snapshots", "estimate_monthly_cost", "check_blast_radius"]
WRITE_TOOLS = ["snapshot_volume"]
DESTRUCTIVE_TOOLS = ["delete_volume", "terminate_instance", "delete_load_balancer", "release_eip", "delete_snapshot"]

mcp = FastMCP("aws-janitor", host=os.getenv("MCP_HOST", "127.0.0.1"), port=int(os.getenv("MCP_PORT", "8000")))


def safe(fn):
    """Never let a raw exception reach the model; return a structured error instead."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — tool boundary
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return wrapper


@mcp.tool(annotations=READ)
@safe
def list_unattached_volumes(region: str = DEFAULT_REGION) -> dict:
    """EBS volumes in 'available' state (not attached to any instance)."""
    return {"region": region, "items": aws_scan.list_unattached_volumes(region)}


@mcp.tool(annotations=READ)
@safe
def list_stopped_instances(region: str = DEFAULT_REGION) -> dict:
    """EC2 instances in 'stopped' state, with the EBS volumes they still pay for."""
    return {"region": region, "items": aws_scan.list_stopped_instances(region)}


@mcp.tool(annotations=READ)
@safe
def list_idle_load_balancers(region: str = DEFAULT_REGION) -> dict:
    """Application/Network load balancers with zero registered targets."""
    return {"region": region, "items": aws_scan.list_idle_load_balancers(region)}


@mcp.tool(annotations=READ)
@safe
def list_unassociated_eips(region: str = DEFAULT_REGION) -> dict:
    """Elastic IPs not associated with any instance or network interface."""
    return {"region": region, "items": aws_scan.list_unassociated_eips(region)}


@mcp.tool(annotations=READ)
@safe
def list_old_snapshots(region: str = DEFAULT_REGION, older_than_days: int | None = None) -> dict:
    """Self-owned EBS snapshots older than N days (default from JANITOR_SNAPSHOT_MIN_AGE_DAYS). Excludes janitor backups."""
    return {"region": region, "items": aws_scan.list_old_snapshots(region, older_than_days)}


@mcp.tool(annotations=READ)
@safe
def estimate_monthly_cost(resources: list[dict], region: str = DEFAULT_REGION) -> dict:
    """Monthly USD cost per resource (pass items from the list_* tools unchanged) plus the total."""
    return pricing.estimate(resources, region)


@mcp.tool(annotations=READ)
@safe
def check_blast_radius(resource_id: str, region: str = DEFAULT_REGION) -> dict:
    """What would break if this resource were deleted. Only propose deletion when safe is true."""
    return aws_blast.check_blast_radius(resource_id, region)


@mcp.tool(annotations=WRITE)
@safe
def snapshot_volume(volume_id: str, region: str = DEFAULT_REGION) -> dict:
    """Create a backup snapshot of a volume before deleting it (reversible, additive)."""
    return aws_actions.snapshot_volume(volume_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def delete_volume(volume_id: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently delete an EBS volume. Irreversible."""
    return aws_actions.delete_volume(volume_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def terminate_instance(instance_id: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently terminate an EC2 instance. Irreversible."""
    return aws_actions.terminate_instance(instance_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def delete_load_balancer(arn: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently delete a load balancer by ARN. Irreversible."""
    return aws_actions.delete_load_balancer(arn, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def release_eip(allocation_id: str, region: str = DEFAULT_REGION) -> dict:
    """Release an Elastic IP. The address cannot be recovered."""
    return aws_actions.release_eip(allocation_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def delete_snapshot(snapshot_id: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently delete an EBS snapshot. Irreversible."""
    return aws_actions.delete_snapshot(snapshot_id, region)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: 4 passed. (If `FastMCP.__init__` rejects `host`/`port` on the installed `mcp` version, set `mcp.settings.host` / `mcp.settings.port` after construction instead.)

- [ ] **Step 5: Smoke-run the server**

Run: `python -m mcp_server.server` then in another shell `curl -i -X POST http://127.0.0.1:8000/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'`
Expected: `HTTP/1.1 200` with a `serverInfo` naming `aws-janitor`.

- [ ] **Step 6: Commit**
```bash
git add mcp_server/server.py tests/test_server.py
git commit -m "feat: expose AWS janitor tools via FastMCP with destructive annotations"
```

---

### Task 6: Seed, cleanup, IAM policy (A; live run by D)

**Files:**
- Create: `scripts/__init__.py` (empty), `scripts/seed_aws.py`, `scripts/cleanup_aws.py`, `scripts/iam-policy.json`, `tests/test_seed_cleanup.py`

**Interfaces:**
- Consumes: `aws_scan.list_*`.
- Produces: `seed(region: str, ami_id: str | None = None) -> dict` returning `{"volumes": [..2], "prod_decoy_volume", "instance", "load_balancer", "target_group", "eip", "snapshot"}`; `cleanup(region: str) -> dict[str, list[str]]` (deleted ids by kind). CLIs: `python -m scripts.seed_aws [--region R] [--ami AMI]`, `python -m scripts.cleanup_aws [--region R]`.

- [ ] **Step 1: Write the failing test** `tests/test_seed_cleanup.py`:
```python
from conftest import REGION

from mcp_server import aws_scan
from scripts.cleanup_aws import cleanup
from scripts.seed_aws import seed


def test_seed_creates_detectable_waste_and_cleanup_removes_it(aws, ami_id):
    ids = seed(REGION, ami_id=ami_id)
    assert set(ids["volumes"]) | {ids["prod_decoy_volume"]} <= {v["id"] for v in aws_scan.list_unattached_volumes(REGION)}
    assert ids["instance"] in {i["id"] for i in aws_scan.list_stopped_instances(REGION)}
    assert ids["load_balancer"] in {i["id"] for i in aws_scan.list_idle_load_balancers(REGION)}
    assert ids["eip"] in {i["id"] for i in aws_scan.list_unassociated_eips(REGION)}
    assert ids["snapshot"] in {i["id"] for i in aws_scan.list_old_snapshots(REGION, older_than_days=0)}

    cleanup(REGION)
    assert not {v["id"] for v in aws_scan.list_unattached_volumes(REGION)} & (set(ids["volumes"]) | {ids["prod_decoy_volume"]})
    assert ids["load_balancer"] not in {i["id"] for i in aws_scan.list_idle_load_balancers(REGION)}
    assert ids["eip"] not in {i["id"] for i in aws_scan.list_unassociated_eips(REGION)}
    assert ids["snapshot"] not in {i["id"] for i in aws_scan.list_old_snapshots(REGION, older_than_days=0)}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_seed_cleanup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.cleanup_aws'`

- [ ] **Step 3: Implement** `scripts/seed_aws.py`:
```python
"""Create tagged demo waste: 2 unattached volumes, 1 prod decoy, 1 stopped instance, 1 idle ALB, 1 EIP, 1 snapshot."""
import argparse
import json

import boto3
from dotenv import load_dotenv

DEMO = {"Key": "janitor-demo", "Value": "true"}
AL2023_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"


def _spec(resource_type, *extra):
    return [{"ResourceType": resource_type, "Tags": [DEMO, *extra]}]


def resolve_ami(region: str, override: str | None) -> str:
    if override:
        return override
    return boto3.client("ssm", region_name=region).get_parameter(Name=AL2023_PARAM)["Parameter"]["Value"]


def seed(region: str, ami_id: str | None = None) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    elb = boto3.client("elbv2", region_name=region)
    vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]}])["Subnets"]
    by_az = {}
    for s in subnets:
        by_az.setdefault(s["AvailabilityZone"], s["SubnetId"])
    az, subnet_ids = next(iter(by_az)), list(by_az.values())[:2]

    vols = [ec2.create_volume(AvailabilityZone=az, Size=size, VolumeType="gp3",
                              TagSpecifications=_spec("volume", {"Key": "Name", "Value": f"janitor-demo-orphan-{n}"}))["VolumeId"]
            for n, size in ((1, 50), (2, 20))]
    decoy = ec2.create_volume(AvailabilityZone=az, Size=100, VolumeType="gp3",
                              TagSpecifications=_spec("volume", {"Key": "env", "Value": "prod"},
                                                      {"Key": "Name", "Value": "janitor-demo-prod-db-backup"}))["VolumeId"]

    iid = ec2.run_instances(ImageId=resolve_ami(region, ami_id), InstanceType="t3.micro", MinCount=1, MaxCount=1,
                            SubnetId=subnet_ids[0], TagSpecifications=_spec("instance", {"Key": "Name", "Value": "janitor-demo-forgotten"}))["Instances"][0]["InstanceId"]
    ec2.get_waiter("instance_running").wait(InstanceIds=[iid])
    ec2.stop_instances(InstanceIds=[iid])
    ec2.get_waiter("instance_stopped").wait(InstanceIds=[iid])

    lb = elb.create_load_balancer(Name="janitor-demo-alb", Subnets=subnet_ids, Type="application", Scheme="internet-facing",
                                  Tags=[DEMO])["LoadBalancers"][0]
    tg = elb.create_target_group(Name="janitor-demo-tg", Protocol="HTTP", Port=80, VpcId=vpc, TargetType="instance",
                                 Tags=[DEMO])["TargetGroups"][0]
    elb.create_listener(LoadBalancerArn=lb["LoadBalancerArn"], Protocol="HTTP", Port=80,
                        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg["TargetGroupArn"]}])

    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.create_tags(Resources=[alloc], Tags=[DEMO])

    snap = ec2.create_snapshot(VolumeId=vols[0], Description="janitor-demo stale snapshot",
                               TagSpecifications=_spec("snapshot"))["SnapshotId"]

    return {"volumes": vols, "prod_decoy_volume": decoy, "instance": iid, "load_balancer": lb["LoadBalancerArn"],
            "target_group": tg["TargetGroupArn"], "eip": alloc, "snapshot": snap}


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--ami", default=None)
    a = p.parse_args()
    print(json.dumps(seed(a.region, a.ami), indent=2))
```

`scripts/cleanup_aws.py`:
```python
"""Delete everything tagged janitor-demo=true (and janitor backups) — run after the demo."""
import argparse
import json

import boto3
from dotenv import load_dotenv

TAG_FILTER = [{"Name": "tag:janitor-demo", "Values": ["true"]}]


def cleanup(region: str) -> dict[str, list[str]]:
    ec2 = boto3.client("ec2", region_name=region)
    elb = boto3.client("elbv2", region_name=region)
    done = {"load_balancers": [], "target_groups": [], "instances": [], "eips": [], "snapshots": [], "volumes": []}

    def is_demo(arn):
        tags = elb.describe_tags(ResourceArns=[arn])["TagDescriptions"][0]["Tags"]
        return {"Key": "janitor-demo", "Value": "true"} in tags

    lbs = [lb["LoadBalancerArn"] for lb in elb.describe_load_balancers()["LoadBalancers"] if is_demo(lb["LoadBalancerArn"])]
    for arn in lbs:
        elb.delete_load_balancer(LoadBalancerArn=arn)
        done["load_balancers"].append(arn)
    if lbs:
        elb.get_waiter("load_balancers_deleted").wait(LoadBalancerArns=lbs)
    for tg in elb.describe_target_groups()["TargetGroups"]:
        if is_demo(tg["TargetGroupArn"]):
            elb.delete_target_group(TargetGroupArn=tg["TargetGroupArn"])
            done["target_groups"].append(tg["TargetGroupArn"])

    iids = [i["InstanceId"] for r in ec2.describe_instances(Filters=TAG_FILTER)["Reservations"] for i in r["Instances"]
            if i["State"]["Name"] != "terminated"]
    if iids:
        ec2.terminate_instances(InstanceIds=iids)
        ec2.get_waiter("instance_terminated").wait(InstanceIds=iids)
        done["instances"] = iids

    for a in ec2.describe_addresses(Filters=TAG_FILTER)["Addresses"]:
        ec2.release_address(AllocationId=a["AllocationId"])
        done["eips"].append(a["AllocationId"])
    for s in ec2.describe_snapshots(OwnerIds=["self"], Filters=TAG_FILTER)["Snapshots"]:
        ec2.delete_snapshot(SnapshotId=s["SnapshotId"])
        done["snapshots"].append(s["SnapshotId"])
    for v in ec2.describe_volumes(Filters=TAG_FILTER + [{"Name": "status", "Values": ["available"]}])["Volumes"]:
        ec2.delete_volume(VolumeId=v["VolumeId"])
        done["volumes"].append(v["VolumeId"])
    return done


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--region", default="us-east-1")
    print(json.dumps(cleanup(p.parse_args().region), indent=2))
```

`scripts/iam-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Discover",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "elasticloadbalancing:Describe*",
        "route53:ListHostedZones",
        "route53:ListResourceRecordSets",
        "ssm:GetParameter"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SeedDemoWaste",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateVolume", "ec2:CreateSnapshot", "ec2:CreateTags", "ec2:RunInstances", "ec2:StopInstances",
        "ec2:AllocateAddress",
        "elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:CreateListener", "elasticloadbalancing:AddTags", "elasticloadbalancing:DeleteTargetGroup"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DestructiveOnlyOnDemoTag",
      "Effect": "Allow",
      "Action": ["ec2:DeleteVolume", "ec2:DeleteSnapshot", "ec2:TerminateInstances", "ec2:ReleaseAddress",
                 "elasticloadbalancing:DeleteLoadBalancer"],
      "Resource": "*",
      "Condition": {"StringEquals": {"aws:ResourceTag/janitor-demo": "true"}}
    }
  ]
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_seed_cleanup.py -v`
Expected: 1 passed.

- [ ] **Step 5: Live seed (D, real AWS)**

Run: `python -m scripts.seed_aws --region us-east-1`
Expected: JSON of 7 ids within ~2 minutes. Verify: `aws ec2 describe-volumes --filters Name=tag:janitor-demo,Values=true --query "Volumes[].VolumeId"` lists 3 volumes (plus the instance root volume once stopped).

- [ ] **Step 6: Commit**
```bash
git add scripts tests/test_seed_cleanup.py
git commit -m "feat: add demo seed/cleanup scripts and least-privilege IAM policy"
```

---

### Task 7: Agent spec + TrueForge bootstrap (D with B)

**Files:**
- Create: `agent/__init__.py` (empty), `agent/instructions.md`, `agent/manifest.py`, `scripts/bootstrap_trueforge.py`, `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `mcp_server.server.DESTRUCTIVE_TOOLS`.
- Produces: `agent.manifest.build_agent_manifest(model_fqn: str) -> dict`; `scripts.bootstrap_trueforge.model_provider_body(api_key, model_id) -> dict`, `mcp_server_body(url) -> dict`, `sandbox_body(api_key) -> dict`, `bootstrap(base_url: str, env: dict, http: httpx.Client | None = None) -> None`. Constants `MODEL_NAME = "janitor-model"`, `MODEL_FQN = "openai/janitor-model"`, `MCP_NAME = "aws-janitor"`.

- [ ] **Step 1: Write** `agent/instructions.md`:
```markdown
You are Cloud Cost Janitor, a careful FinOps engineer for an AWS account.

Goal: find idle resources in the requested region, price them, produce a teardown plan, and clean up
ONLY what a human approves. You never guess; you use the aws-janitor tools.

Procedure — follow in order:
1. Discover: call list_unattached_volumes, list_stopped_instances, list_idle_load_balancers,
   list_unassociated_eips and list_old_snapshots for the region.
2. Price: call estimate_monthly_cost with ALL discovered items (pass them unchanged).
3. Analyse in the sandbox: write and run a Python script that loads the priced items (write them to
   items.json first), ranks them by monthly_cost, computes the total and annual waste, and writes
   teardown-plan.md (table: resource, kind, $/month, age, action) and teardown-plan.csv.
   Always do this step in the sandbox, even for small lists.
4. Safety: call check_blast_radius for every candidate. If safe is false, EXCLUDE it and say why
   (e.g. "vol-… skipped: tagged env=prod"). Never propose deleting an unsafe resource.
5. Act: for each safe candidate, in order of monthly_cost descending:
   - EBS volume: call snapshot_volume first, then delete_volume.
   - stopped instance: terminate_instance.  - load balancer: delete_load_balancer (use the ARN).
   - Elastic IP: release_eip.  - snapshot: delete_snapshot.
   Destructive calls pause for human approval. That is expected — issue them and wait.
6. Respect decisions: if a call is denied, do not retry it or try an alternative way to remove the
   resource. Record the denial and the reason.
7. Report: finish with a markdown summary: a table of every candidate with outcome
   (deleted / denied / skipped-unsafe / failed), monthly savings achieved, savings declined,
   and any errors verbatim.

Rules: be concise between tool calls. Never invent resource ids. If a tool returns ok=false, report
the error and move on; do not retry more than once.
```

- [ ] **Step 2: Write the failing test** `tests/test_bootstrap.py`:
```python
import httpx

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
    assert m["model"]["name"] == "openai/janitor-model"
    assert "Cloud Cost Janitor" in m["instructions"]


def test_bodies():
    assert bt.model_provider_body("sk", "gpt-5.2") == {"manifest": {
        "type": "openai", "auth": {"api_key": "sk"},
        "models": [{"name": "janitor-model", "model_id": "gpt-5.2", "properties": {}}]}}
    assert bt.mcp_server_body("http://localhost:8000/mcp")["manifest"]["type"] == "remote"
    assert bt.sandbox_body("dk") == {"manifest": {"type": "daytona", "auth": {"api_key": "dk"}}}


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
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/test_bootstrap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.manifest'`

- [ ] **Step 4: Implement** `agent/manifest.py`:
```python
from pathlib import Path

from mcp_server.server import DESTRUCTIVE_TOOLS

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")


def build_agent_manifest(model_fqn: str) -> dict:
    return {
        "model": {"name": model_fqn, "params": {"temperature": 0.1}},
        "instructions": INSTRUCTIONS,
        "mcp_servers": [{
            "name": "aws-janitor",
            "enable_tools": ["@all"],
            "preload": True,
            # Annotation gate plus explicit names: defense in depth if annotations are ever dropped.
            "require_approval_for_tools": ["@destructive", *DESTRUCTIVE_TOOLS],
        }],
        "config": {
            "sandbox": {"enabled": True},
            "generative_ui": {"enabled": False},
            "ask_user_questions": {"enabled": True},
            "dynamic_sub_agents": {"enabled": False},
            "iteration_limit": 60,
        },
    }
```

`scripts/bootstrap_trueforge.py`:
```python
"""Configure a local TrueForge server for Cloud Cost Janitor. Safe to re-run."""
import os
import sys

import httpx
from dotenv import load_dotenv

from agent.manifest import build_agent_manifest

MODEL_NAME = "janitor-model"
MODEL_FQN = f"openai/{MODEL_NAME}"
MCP_NAME = "aws-janitor"


def model_provider_body(api_key: str, model_id: str) -> dict:
    return {"manifest": {"type": "openai", "auth": {"api_key": api_key},
                         "models": [{"name": MODEL_NAME, "model_id": model_id, "properties": {}}]}}


def mcp_server_body(url: str) -> dict:
    return {"manifest": {"type": "remote", "name": MCP_NAME, "url": url,
                         "description": "AWS cost cleanup: discover idle resources, price them, check blast radius, delete with approval."}}


def sandbox_body(api_key: str) -> dict:
    return {"manifest": {"type": "daytona", "auth": {"api_key": api_key}}}


def _check(resp: httpx.Response, what: str) -> httpx.Response:
    if resp.status_code >= 400:
        sys.exit(f"{what} failed: HTTP {resp.status_code} {resp.text}\nCompare with {resp.request.url.scheme}://{resp.request.url.host}:{resp.request.url.port}/api/v1/docs")
    print(f"ok  {what}")
    return resp


def bootstrap(base_url: str, env: dict, http: httpx.Client | None = None) -> None:
    http = http or httpx.Client(base_url=base_url, timeout=60)
    _check(http.put("/api/v1/settings/model-providers", json=model_provider_body(env["OPENAI_API_KEY"], env["OPENAI_MODEL_ID"])), "model provider")
    _check(http.put("/api/v1/settings/mcp-servers", json=mcp_server_body(env["MCP_PUBLIC_URL"])), "mcp server")
    _check(http.put("/api/v1/settings/sandbox-providers", json=sandbox_body(env["DAYTONA_API_KEY"])), "sandbox provider")

    name = env["AGENT_NAME"]
    manifest = build_agent_manifest(MODEL_FQN)
    existing = _check(http.get("/api/v1/agents", params={"agent_name": name}), "list agents").json()["data"]
    match = next((a for a in existing if a["name"] == name), None)
    description = "Finds idle AWS resources, prices them, and deletes only what a human approves."
    if match:
        _check(http.put(f"/api/v1/agents/{match['id']}", json={"description": description, "manifest": manifest}), "update agent")
    else:
        _check(http.post("/api/v1/agents", json={"name": name, "description": description, "manifest": manifest}), "create agent")


if __name__ == "__main__":
    load_dotenv()
    bootstrap(os.getenv("TRUEFORGE_BASE_URL", "http://localhost:8790"), dict(os.environ))
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_bootstrap.py -v`
Expected: 4 passed

- [ ] **Step 6: Live bootstrap** (TrueForge and MCP server running, `.env` filled)

Run: `python -m scripts.bootstrap_trueforge`
Expected: five `ok` lines. If any call returns 400, open `http://localhost:8790/api/v1/docs`, compare the schema for that endpoint, fix the body builder AND its test, and re-run. Then open TrueForge UI → Agents → `cloud-cost-janitor` → Overview: the five delete tools show the approval shield.

- [ ] **Step 7: Harness smoke test in TrueForge's own UI** — chat with the agent: "Run the cleanup for us-east-1." Expected: list tools run, a sandbox is created, it pauses on the first delete with Allow/Deny. This proves the harness before our UI exists.

- [ ] **Step 8: Commit**
```bash
git add agent scripts/bootstrap_trueforge.py tests/test_bootstrap.py
git commit -m "feat: add agent spec and idempotent TrueForge bootstrap"
```

---

### Task 8: Event normalizer (B)

**Files:**
- Create: `api/__init__.py` (empty), `api/events.py`, `tests/test_events.py`

**Interfaces:**
- Consumes: TrueForge event dicts (wire format, snake_case) — `model.message{id, thread_id, content, tool_calls:[{id, function:{name, arguments}, tool_info?:{name}}]}`, `tool.response{tool_call_id, content}`, `tool.approval_required{thread_id, tool_calls:[{id, source_event_id}]}`, `sandbox.created`, `thread.created{title}`, `turn.created`, `turn.done{state}`.
- Produces: `class Normalizer` with `feed(event: dict, index: dict[str, dict]) -> list[dict]` emitting the spec §4.4 UI events; helpers `short_tool_name(call: dict) -> str`, `parse_content(content) -> Any`, `find_call(index, call_id) -> dict | None`, `resource_id_from_args(args: dict) -> str | None`.

- [ ] **Step 1: Write the failing test** `tests/test_events.py`:
```python
import json

from api.events import Normalizer, parse_content, short_tool_name


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
    assert br[-1] == {"type": "resources", "items": [{"id": "vol-9", "blast_radius": "tagged env=prod"}]}


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


def test_lifecycle_events():
    n = Normalizer()
    assert n.feed({"type": "turn.created", "id": "t"}, {}) == [{"type": "status", "status": "running"}]
    assert n.feed({"type": "sandbox.created", "id": "s", "sandbox_id": "sb1"}, {})[0]["kind"] == "sandbox"
    assert n.feed({"type": "thread.created", "id": "th", "title": "pricing"}, {})[0]["kind"] == "subagent"
    assert n.feed({"type": "mcp.initialize", "id": "i"}, {}) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.events'`

- [ ] **Step 3: Implement** `api/events.py`:
```python
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
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except ValueError:
        return {"raw": raw}


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
            return [{"type": "message", "id": event["id"], "content": event["content"]}] if event.get("content") else []
        if t == "tool.response":
            return self._tool_response(event, index)
        if t == "tool.approval_required":
            return self._approvals(event, index)
        if t == "sandbox.created":
            return [{"type": "step", "id": event["id"], "kind": "sandbox", "title": "Sandbox provisioned",
                     "detail": {"sandbox_id": event.get("sandbox_id")}}]
        if t == "thread.created":
            return [{"type": "step", "id": event["id"], "kind": "subagent", "title": event.get("title", "subagent"), "detail": {}}]
        if t == "turn.done":
            return self._done(event.get("state") or {})
        return []

    def _tool_response(self, event, index):
        call = find_call(index, event.get("tool_call_id"))
        tool = short_tool_name(call) if call else "tool"
        result = parse_content(event.get("content"))
        out = [{"type": "step", "id": event["id"], "kind": _kind(tool), "title": tool,
                "detail": {"args": _args(call) if call else {}, "result": result}}]
        if tool in LIST_TOOLS and isinstance(result, dict) and isinstance(result.get("items"), list):
            out.append({"type": "resources", "items": result["items"]})
        if tool == "check_blast_radius" and isinstance(result, dict) and "resource_id" in result:
            label = "safe" if result.get("safe") else "; ".join(result.get("reasons") or ["unsafe"])
            out.append({"type": "resources", "items": [{"id": result["resource_id"], "blast_radius": label}]})
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
        if status == "done" and state.get("required_actions"):
            return [{"type": "status", "status": "paused"}]
        if status == "done":
            output = (state.get("output") or {}).get("content") or ""
            return [{"type": "done", "output": output}, {"type": "status", "status": "done"}]
        message = state.get("message") or state.get("reason") or status
        return [{"type": "status", "status": "error", "message": message}]
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_events.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**
```bash
git add api/__init__.py api/events.py tests/test_events.py
git commit -m "feat: normalize TrueForge turn events for the dashboard"
```

---

### Task 9: Session runner + FastAPI bridge (B)

**Files:**
- Create: `api/runner.py`, `api/main.py`, `tests/test_runner.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `api.events.Normalizer`; `trueforge_sdk.TrueForge` client (`sessions.create(agent={"name"})` → `.data.id`; `sessions.create_turn_stream(session_id=, input=)` → iterable of events with `.type`, `.id`, `model_dump()`); `trueforge_sdk.events.merge_event_delta`.
- Produces:
  - `SessionRunner(client, agent_name: str, loop: asyncio.AbstractEventLoop | None)` with `.start(prompt: str) -> str` (session id), `.decide(decisions: list[dict]) -> None` (each `{tool_call_id, thread_id, allow: bool, reason?: str}`), `.subscribe() -> asyncio.Queue`, `.unsubscribe(q)`, `.buffer: list[dict]`, `.audit: list[dict]`, `.pending: list[dict]`, `.wait(timeout: float) -> None`.
  - HTTP: `POST /api/scan {region}` → `{session_id}`; `GET /api/sessions/{id}/events` (SSE, `data:` = JSON UI event); `POST /api/sessions/{id}/decisions {decisions:[...]}` → `{ok: true}`; `GET /api/sessions/{id}/audit` → `{audit:[...]}`; `GET /api/health` → `{trueforge: bool, mcp: bool}`.
  - Run: `uvicorn api.main:app --port 8080`

- [ ] **Step 1: Write the failing test** `tests/test_runner.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.runner'`

- [ ] **Step 3: Implement** `api/runner.py`:
```python
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

    def decide(self, decisions: list[dict]) -> None:
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
        try:
            stream = self.client.sessions.create_turn_stream(session_id=self.session_id, input=input_items)
            for ev in stream:
                self._handle(ev)
        except Exception as e:  # noqa: BLE001 — surface any SDK/network failure to the UI
            self._publish({"type": "status", "status": "error", "message": f"{type(e).__name__}: {e}"})

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
            dump = os.getenv("JANITOR_DUMP_EVENTS")
            if dump:  # capture real (non-delta) events to lock normalizer tests to TrueForge's actual shapes
                with open(dump, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, default=str) + "\n")
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_runner.py -v`
Expected: 2 passed

- [ ] **Step 5: Write the failing test** `tests/test_main.py`:
```python
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
```

- [ ] **Step 6: Run to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `ImportError: cannot import name 'main'`

- [ ] **Step 7: Implement** `api/main.py`:
```python
"""HTTP bridge between the dashboard and TrueForge."""
import asyncio
import json
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.runner import SessionRunner

load_dotenv()

TRUEFORGE_BASE_URL = os.getenv("TRUEFORGE_BASE_URL", "http://localhost:8790")
MCP_PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", "http://localhost:8000/mcp")
AGENT_NAME = os.getenv("AGENT_NAME", "cloud-cost-janitor")
RUNNERS: dict[str, SessionRunner] = {}

app = FastAPI(title="Cloud Cost Janitor API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

_client = None


def get_client():
    global _client
    if _client is None:
        from trueforge_sdk import TrueForge
        _client = TrueForge(base_url=TRUEFORGE_BASE_URL, timeout=600)
    return _client


class ScanRequest(BaseModel):
    region: str = "us-east-1"


class Decision(BaseModel):
    tool_call_id: str
    thread_id: str
    allow: bool
    reason: str | None = None


class DecisionsRequest(BaseModel):
    decisions: list[Decision]


def _runner(session_id: str) -> SessionRunner:
    runner = RUNNERS.get(session_id)
    if runner is None:
        raise HTTPException(404, "unknown session")
    return runner


def scan_prompt(region: str) -> str:
    return (f"Run a cost cleanup for AWS region {region}. Follow your procedure: discover, price, "
            f"build the teardown plan in the sandbox, check blast radius, then request deletion of safe candidates.")


@app.post("/api/scan")
async def scan(req: ScanRequest):
    runner = SessionRunner(get_client(), AGENT_NAME, asyncio.get_running_loop())
    session_id = await run_in_threadpool(runner.start, scan_prompt(req.region))
    RUNNERS[session_id] = runner
    return {"session_id": session_id}


@app.get("/api/sessions/{session_id}/events")
async def events(session_id: str):
    runner = _runner(session_id)
    queue = runner.subscribe()

    async def gen():
        try:
            while True:
                event = await queue.get()
                yield {"data": json.dumps(event)}
        finally:
            runner.unsubscribe(queue)

    return EventSourceResponse(gen(), ping=15)


@app.post("/api/sessions/{session_id}/decisions")
async def decisions(session_id: str, req: DecisionsRequest):
    runner = _runner(session_id)
    await run_in_threadpool(runner.decide, [d.model_dump() for d in req.decisions])
    return {"ok": True}


@app.get("/api/sessions/{session_id}/audit")
async def audit(session_id: str):
    return {"audit": _runner(session_id).audit}


@app.get("/api/health")
async def health():
    async def up(url):
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                await c.get(url)
            return True
        except httpx.HTTPError:
            return False
    return {"trueforge": await up(f"{TRUEFORGE_BASE_URL}/api/v1/agents"), "mcp": await up(MCP_PUBLIC_URL)}
```

- [ ] **Step 8: Run to verify it passes**

Run: `pytest tests/test_main.py tests/test_runner.py -v`
Expected: 4 passed

- [ ] **Step 9: Live check** (TrueForge + MCP + bootstrap done)

Run: `mkdir -p tests/fixtures && JANITOR_DUMP_EVENTS=tests/fixtures/real_turn.jsonl uvicorn api.main:app --port 8080`, then `curl -s -X POST localhost:8080/api/scan -H "Content-Type: application/json" -d '{"region":"us-east-1"}'` and `curl -N localhost:8080/api/sessions/<id>/events`
Expected: stream of `data: {...}` lines ending with `{"type": "status", "status": "paused"}` after one or more `approval` events. If events arrive but `approval.tool` is `"unknown"`, print one raw `model.message` dict (add a temporary `print(event)` in `_handle`) and adjust `short_tool_name`/`find_call` plus their tests to the real field names.

- [ ] **Step 10: Lock the normalizer to the real stream.** Stop uvicorn once the stream has paused. Check `tests/fixtures/real_turn.jsonl` for secrets (`grep -E "sk-|AKIA" tests/fixtures/real_turn.jsonl` must print nothing), then add to `tests/test_events.py`:
```python
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "real_turn.jsonl"


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
```
Run: `pytest tests/test_events.py -v`. If it fails, fix `api/events.py` (not the fixture) until it passes, and keep the other normalizer tests green.

- [ ] **Step 11: Commit**
```bash
git add api tests/test_runner.py tests/test_main.py tests/test_events.py tests/fixtures/real_turn.jsonl
git commit -m "feat: add TrueForge session runner and FastAPI SSE bridge"
```

---

### Task 10: Web scaffold, types, state reducer (C)

**Files:**
- Create: `web/` (Vite React TS template), `web/vite.config.ts` (overwrite), `web/src/index.css` (overwrite), `web/src/types.ts`, `web/src/state.ts`, `web/src/state.test.ts`

**Interfaces:**
- Consumes: UI event contract from Task 8 (`status | step | message | approval | resources | done`).
- Produces: `types.ts` exports `Status, Step, Resource, Approval, AuditEntry, ServerEvent`; `state.ts` exports `State`, `initialState`, `reduce(state: State, action: ServerEvent | {type:'reset'} | {type:'decided'}): State`.

- [ ] **Step 1: Scaffold**

Run (from repo root):
```bash
npm create vite@latest web -- --template react-ts
cd web && npm install && npm install react-markdown && npm install -D tailwindcss @tailwindcss/vite vitest
```
Expected: `web/package.json` exists. Add to its `"scripts"`: `"test": "vitest run"`.

- [ ] **Step 2: Config** — `web/vite.config.ts`:
```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8080' } },
  test: { environment: 'node' },
})
```
`web/src/index.css`:
```css
@import "tailwindcss";
body { @apply bg-slate-950 text-slate-100; }
```

- [ ] **Step 3: Types** — `web/src/types.ts`:
```ts
export type Status = 'idle' | 'running' | 'paused' | 'done' | 'error'

export interface Step { id: string; kind: 'tool' | 'sandbox' | 'message' | 'subagent'; title: string; detail: unknown }

export interface Resource {
  id: string
  kind?: 'ebs' | 'snapshot' | 'eip' | 'lb' | 'ec2_stopped'
  monthly_cost?: number
  blast_radius?: string
  age_days?: number
  size_gb?: number
  name?: string
  tags?: Record<string, string>
}

export interface Approval { tool_call_id: string; thread_id: string; tool: string; args: Record<string, unknown>; resource_id: string | null }

export interface AuditEntry { at: string; tool: string; resource_id: string | null; decision: 'approved' | 'denied'; reason?: string }

export type ServerEvent =
  | { type: 'status'; status: Status; message?: string }
  | ({ type: 'step' } & Step)
  | { type: 'message'; id: string; content: string }
  | ({ type: 'approval' } & Approval)
  | { type: 'resources'; items: Resource[] }
  | { type: 'done'; output: string }
```

- [ ] **Step 4: Write the failing test** — `web/src/state.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { initialState, reduce } from './state'

describe('reduce', () => {
  it('merges resources by id across events', () => {
    let s = reduce(initialState, { type: 'resources', items: [{ id: 'vol-1', kind: 'ebs', size_gb: 50 }] })
    s = reduce(s, { type: 'resources', items: [{ id: 'vol-1', monthly_cost: 4 }] })
    s = reduce(s, { type: 'resources', items: [{ id: 'vol-1', blast_radius: 'safe' }] })
    expect(s.resources['vol-1']).toEqual({ id: 'vol-1', kind: 'ebs', size_gb: 50, monthly_cost: 4, blast_radius: 'safe' })
  })

  it('dedupes approvals and clears them on decided', () => {
    const a = { type: 'approval' as const, tool_call_id: 'c1', thread_id: 'main', tool: 'delete_volume', args: {}, resource_id: 'vol-1' }
    let s = reduce(reduce(initialState, a), a)
    expect(s.approvals).toHaveLength(1)
    s = reduce(s, { type: 'decided' })
    expect(s.approvals).toHaveLength(0)
  })

  it('upserts steps and messages, keeps order', () => {
    let s = reduce(initialState, { type: 'message', id: 'm1', content: 'Sca' })
    s = reduce(s, { type: 'message', id: 'm1', content: 'Scanning' })
    s = reduce(s, { type: 'step', id: 's1', kind: 'tool', title: 'list_unattached_volumes', detail: {} })
    expect(s.messages).toEqual({ m1: 'Scanning' })
    expect(s.feed).toEqual([{ kind: 'message', id: 'm1' }, { kind: 'step', id: 's1' }])
  })

  it('tracks status, error and output; reset clears everything', () => {
    let s = reduce(initialState, { type: 'status', status: 'error', message: 'boom' })
    expect(s.status).toBe('error'); expect(s.error).toBe('boom')
    s = reduce(s, { type: 'done', output: '## Summary' })
    expect(s.output).toBe('## Summary')
    expect(reduce(s, { type: 'reset' })).toEqual(initialState)
  })
})
```

- [ ] **Step 5: Run to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot resolve `./state`

- [ ] **Step 6: Implement** — `web/src/state.ts`:
```ts
import type { Approval, Resource, ServerEvent, Status, Step } from './types'

export interface FeedItem { kind: 'step' | 'message'; id: string }

export interface State {
  status: Status
  error?: string
  steps: Record<string, Step>
  messages: Record<string, string>
  feed: FeedItem[]
  resources: Record<string, Resource>
  approvals: Approval[]
  output?: string
}

export const initialState: State = { status: 'idle', steps: {}, messages: {}, feed: [], resources: {}, approvals: [] }

export type Action = ServerEvent | { type: 'reset' } | { type: 'decided' }

function addToFeed(feed: FeedItem[], item: FeedItem): FeedItem[] {
  return feed.some((f) => f.kind === item.kind && f.id === item.id) ? feed : [...feed, item]
}

export function reduce(s: State, a: Action): State {
  switch (a.type) {
    case 'reset':
      return initialState
    case 'decided':
      return { ...s, approvals: [] }
    case 'status':
      return { ...s, status: a.status, error: a.status === 'error' ? a.message : undefined }
    case 'step': {
      const { type: _t, ...step } = a
      return { ...s, steps: { ...s.steps, [a.id]: step }, feed: addToFeed(s.feed, { kind: 'step', id: a.id }) }
    }
    case 'message':
      return { ...s, messages: { ...s.messages, [a.id]: a.content }, feed: addToFeed(s.feed, { kind: 'message', id: a.id }) }
    case 'resources': {
      const resources = { ...s.resources }
      for (const r of a.items) resources[r.id] = { ...resources[r.id], ...r }
      return { ...s, resources }
    }
    case 'approval': {
      if (s.approvals.some((x) => x.tool_call_id === a.tool_call_id)) return s
      const { type: _t, ...approval } = a
      return { ...s, approvals: [...s.approvals, approval] }
    }
    case 'done':
      return { ...s, output: a.output }
  }
}
```

- [ ] **Step 7: Run to verify it passes**

Run: `cd web && npm test`
Expected: 4 passed

- [ ] **Step 8: Commit**
```bash
git add web
git commit -m "feat: scaffold dashboard with typed event reducer"
```

---

### Task 11: Dashboard components (C)

**Files:**
- Create: `web/src/api.ts`, `web/src/useSession.ts`, `web/src/components/{KpiStrip,ScanPanel,AgentFeed,ResourceTable,ApprovalCards,PlanView,AuditTrail}.tsx`
- Modify (overwrite): `web/src/App.tsx`, `web/src/main.tsx`; delete `web/src/App.css`

**Interfaces:**
- Consumes: `State`, `reduce`, `initialState` (Task 10); HTTP endpoints (Task 9).
- Produces: the page described in spec §4.3.

- [ ] **Step 1: API client** — `web/src/api.ts`:
```ts
export interface DecisionInput { tool_call_id: string; thread_id: string; allow: boolean; reason?: string }

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
  return r.json()
}

export const startScan = (region: string) => post<{ session_id: string }>('/api/scan', { region })
export const sendDecisions = (sessionId: string, decisions: DecisionInput[]) =>
  post<{ ok: boolean }>(`/api/sessions/${sessionId}/decisions`, { decisions })
export const getHealth = async () => (await fetch('/api/health')).json() as Promise<{ trueforge: boolean; mcp: boolean }>
```

- [ ] **Step 2: Session hook** — `web/src/useSession.ts`:
```ts
import { useCallback, useEffect, useReducer, useState } from 'react'
import { initialState, reduce } from './state'
import { sendDecisions, startScan, type DecisionInput } from './api'
import type { AuditEntry } from './types'

export function useSession() {
  const [state, dispatch] = useReducer(reduce, initialState)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])

  useEffect(() => {
    if (!sessionId) return
    const es = new EventSource(`/api/sessions/${sessionId}/events`)
    es.onmessage = (m) => dispatch(JSON.parse(m.data))
    return () => es.close()
  }, [sessionId])

  const scan = useCallback(async (region: string) => {
    dispatch({ type: 'reset' })
    setAudit([])
    dispatch({ type: 'status', status: 'running' })
    try {
      setSessionId((await startScan(region)).session_id)
    } catch (e) {
      dispatch({ type: 'status', status: 'error', message: String(e) })
    }
  }, [])

  const decide = useCallback(async (decisions: DecisionInput[]) => {
    if (!sessionId) return
    const at = new Date().toISOString()
    setAudit((prev) => [
      ...prev,
      ...decisions.map((d) => {
        const a = state.approvals.find((x) => x.tool_call_id === d.tool_call_id)
        return { at, tool: a?.tool ?? '?', resource_id: a?.resource_id ?? null, decision: d.allow ? 'approved' : 'denied', reason: d.reason } as AuditEntry
      }),
    ])
    dispatch({ type: 'decided' })
    await sendDecisions(sessionId, decisions)
  }, [sessionId, state.approvals])

  return { state, audit, scan, decide }
}
```

- [ ] **Step 3: Components**

`web/src/components/KpiStrip.tsx`:
```tsx
import type { AuditEntry, Resource } from '../types'

const usd = (n: number) => `$${n.toFixed(2)}`

export function KpiStrip({ resources, audit, pending }: { resources: Resource[]; audit: AuditEntry[]; pending: number }) {
  const waste = resources.reduce((t, r) => t + (r.monthly_cost ?? 0), 0)
  const byId = Object.fromEntries(resources.map((r) => [r.id, r]))
  const saved = audit.filter((a) => a.decision === 'approved').reduce((t, a) => t + (byId[a.resource_id ?? '']?.monthly_cost ?? 0), 0)
  const tiles = [
    ['Idle resources', String(resources.filter((r) => r.kind).length)],
    ['Monthly waste', usd(waste)],
    ['Approved savings / mo', usd(saved)],
    ['Pending approvals', String(pending)],
  ]
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {tiles.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
      ))}
    </div>
  )
}
```

`web/src/components/ScanPanel.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { getHealth } from '../api'
import type { Status } from '../types'

export function ScanPanel({ status, error, onScan }: { status: Status; error?: string; onScan: (region: string) => void }) {
  const [region, setRegion] = useState('us-east-1')
  const [health, setHealth] = useState<{ trueforge: boolean; mcp: boolean } | null>(null)
  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth({ trueforge: false, mcp: false })) }, [])
  const ready = health?.trueforge && health?.mcp
  const busy = status === 'running'
  return (
    <div className="flex flex-wrap items-center gap-3">
      <select value={region} onChange={(e) => setRegion(e.target.value)} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
        {['us-east-1', 'us-west-2', 'ap-south-1', 'eu-west-1'].map((r) => <option key={r}>{r}</option>)}
      </select>
      <button disabled={!ready || busy} onClick={() => onScan(region)}
        className="rounded-lg bg-emerald-600 px-4 py-2 font-medium hover:bg-emerald-500 disabled:opacity-40">
        {busy ? 'Janitor running…' : 'Run janitor'}
      </button>
      <span className="text-sm text-slate-400">
        TrueForge {health?.trueforge ? '🟢' : '🔴'} · MCP {health?.mcp ? '🟢' : '🔴'} · status: <b>{status}</b>
      </span>
      {error && <span className="text-sm text-rose-400">{error}</span>}
    </div>
  )
}
```

`web/src/components/AgentFeed.tsx`:
```tsx
import type { State } from '../state'

const badge: Record<string, string> = { tool: 'bg-sky-900 text-sky-200', sandbox: 'bg-violet-900 text-violet-200', subagent: 'bg-amber-900 text-amber-200' }

export function AgentFeed({ state }: { state: State }) {
  return (
    <div className="max-h-[28rem] space-y-2 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900 p-3 text-sm">
      {state.feed.length === 0 && <div className="text-slate-500">Agent steps will stream here.</div>}
      {state.feed.map((f) => {
        if (f.kind === 'message') return <div key={`m-${f.id}`} className="whitespace-pre-wrap text-slate-300">{state.messages[f.id]}</div>
        const s = state.steps[f.id]
        return (
          <details key={`s-${f.id}`} className="rounded-lg bg-slate-950 p-2">
            <summary className="cursor-pointer">
              <span className={`mr-2 rounded px-1.5 py-0.5 text-xs ${badge[s.kind] ?? ''}`}>{s.kind}</span>{s.title}
            </summary>
            <pre className="mt-2 overflow-x-auto text-xs text-slate-400">{JSON.stringify(s.detail, null, 2)}</pre>
          </details>
        )
      })}
    </div>
  )
}
```

`web/src/components/ResourceTable.tsx`:
```tsx
import type { Resource } from '../types'

export function ResourceTable({ resources }: { resources: Resource[] }) {
  const rows = resources.filter((r) => r.kind).sort((a, b) => (b.monthly_cost ?? 0) - (a.monthly_cost ?? 0))
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900 text-slate-400">
          <tr><th className="p-2">Kind</th><th className="p-2">Resource</th><th className="p-2">$/mo</th><th className="p-2">Age</th><th className="p-2">Blast radius</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-slate-800">
              <td className="p-2">{r.kind}</td>
              <td className="p-2 font-mono text-xs">{r.name ?? r.tags?.Name ?? r.id}</td>
              <td className="p-2">{r.monthly_cost != null ? `$${r.monthly_cost.toFixed(2)}` : '—'}</td>
              <td className="p-2">{r.age_days != null ? `${r.age_days}d` : '—'}</td>
              <td className={`p-2 ${r.blast_radius && r.blast_radius !== 'safe' ? 'text-rose-400' : 'text-emerald-400'}`}>{r.blast_radius ?? '—'}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={5} className="p-3 text-slate-500">No resources yet.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
```

`web/src/components/ApprovalCards.tsx`:
```tsx
import { useState } from 'react'
import type { DecisionInput } from '../api'
import type { Approval, Resource } from '../types'

export function ApprovalCards({ approvals, resources, onSubmit }: {
  approvals: Approval[]; resources: Record<string, Resource>; onSubmit: (d: DecisionInput[]) => void
}) {
  const [choice, setChoice] = useState<Record<string, { allow: boolean; reason: string }>>({})
  if (approvals.length === 0) return null
  const all = approvals.every((a) => choice[a.tool_call_id])
  const set = (id: string, allow: boolean) => setChoice((c) => ({ ...c, [id]: { allow, reason: c[id]?.reason ?? '' } }))
  return (
    <div className="space-y-3 rounded-xl border-2 border-amber-500 bg-amber-950/30 p-4">
      <h2 className="text-lg font-semibold text-amber-300">⏸ Agent paused — irreversible actions need your approval</h2>
      {approvals.map((a) => {
        const r = a.resource_id ? resources[a.resource_id] : undefined
        const c = choice[a.tool_call_id]
        return (
          <div key={a.tool_call_id} className="rounded-lg border border-slate-700 bg-slate-900 p-3">
            <div className="font-mono text-sm"><b className="text-rose-300">{a.tool}</b> {a.resource_id}</div>
            <div className="mt-1 text-sm text-slate-300">
              Cost: <b>{r?.monthly_cost != null ? `$${r.monthly_cost.toFixed(2)}/mo` : 'unknown'}</b> · Blast radius: <b>{r?.blast_radius ?? 'not checked'}</b>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button onClick={() => set(a.tool_call_id, true)} className={`rounded px-3 py-1 ${c?.allow === true ? 'bg-emerald-600' : 'bg-slate-700'}`}>Approve</button>
              <button onClick={() => set(a.tool_call_id, false)} className={`rounded px-3 py-1 ${c?.allow === false ? 'bg-rose-600' : 'bg-slate-700'}`}>Deny</button>
              {c?.allow === false && (
                <input placeholder="reason" value={c.reason} className="flex-1 rounded bg-slate-800 px-2 py-1 text-sm"
                  onChange={(e) => setChoice((x) => ({ ...x, [a.tool_call_id]: { allow: false, reason: e.target.value } }))} />
              )}
            </div>
          </div>
        )
      })}
      <button disabled={!all} className="rounded-lg bg-amber-500 px-4 py-2 font-medium text-slate-950 disabled:opacity-40"
        onClick={() => { onSubmit(approvals.map((a) => ({ tool_call_id: a.tool_call_id, thread_id: a.thread_id, allow: choice[a.tool_call_id].allow, reason: choice[a.tool_call_id].reason || undefined }))); setChoice({}) }}>
        Submit decisions
      </button>
    </div>
  )
}
```

`web/src/components/PlanView.tsx`:
```tsx
import Markdown from 'react-markdown'

export function PlanView({ output }: { output?: string }) {
  if (!output) return null
  return <div className="prose prose-invert max-w-none rounded-xl border border-slate-800 bg-slate-900 p-4"><Markdown>{output}</Markdown></div>
}
```

`web/src/components/AuditTrail.tsx`:
```tsx
import type { AuditEntry } from '../types'

export function AuditTrail({ audit }: { audit: AuditEntry[] }) {
  if (audit.length === 0) return null
  return (
    <ul className="space-y-1 rounded-xl border border-slate-800 bg-slate-900 p-3 text-sm">
      {audit.map((a, i) => (
        <li key={i}>
          <span className="text-slate-500">{a.at}</span> · <b className={a.decision === 'approved' ? 'text-emerald-400' : 'text-rose-400'}>{a.decision}</b> · {a.tool} {a.resource_id}
          {a.reason && <span className="text-slate-400"> — “{a.reason}”</span>}
        </li>
      ))}
    </ul>
  )
}
```

- [ ] **Step 4: App** — `web/src/App.tsx`:
```tsx
import { AgentFeed } from './components/AgentFeed'
import { ApprovalCards } from './components/ApprovalCards'
import { AuditTrail } from './components/AuditTrail'
import { KpiStrip } from './components/KpiStrip'
import { PlanView } from './components/PlanView'
import { ResourceTable } from './components/ResourceTable'
import { ScanPanel } from './components/ScanPanel'
import { useSession } from './useSession'

export default function App() {
  const { state, audit, scan, decide } = useSession()
  const resources = Object.values(state.resources)
  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 md:p-8">
      <header>
        <h1 className="text-3xl font-bold">🧹 Cloud Cost Janitor</h1>
        <p className="text-slate-400">Finds idle AWS spend, plans the teardown in a sandbox, and deletes nothing without your approval. Powered by TrueForge.</p>
      </header>
      <ScanPanel status={state.status} error={state.error} onScan={scan} />
      <KpiStrip resources={resources} audit={audit} pending={state.approvals.length} />
      <ApprovalCards approvals={state.approvals} resources={state.resources} onSubmit={decide} />
      <div className="grid gap-5 lg:grid-cols-2">
        <section><h2 className="mb-2 font-semibold">Idle resources</h2><ResourceTable resources={resources} /></section>
        <section><h2 className="mb-2 font-semibold">Agent steps</h2><AgentFeed state={state} /></section>
      </div>
      <section><h2 className="mb-2 font-semibold">Report</h2><PlanView output={state.output} /></section>
      <section><h2 className="mb-2 font-semibold">Audit trail</h2><AuditTrail audit={audit} /></section>
    </main>
  )
}
```

`web/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
```
Delete `web/src/App.css`.

- [ ] **Step 5: Verify build + tests**

Run: `cd web && npm test && npm run build`
Expected: 4 tests pass; `tsc -b && vite build` succeeds with no type errors. (If `noUnusedLocals` flags the `_t` destructures in `state.ts`, rename to a used pattern: `const step: Step = { id: a.id, kind: a.kind, title: a.title, detail: a.detail }`.)

- [ ] **Step 6: Visual check** — `npm run dev`, open http://localhost:5173 with the API down: page renders, health shows 🔴, button disabled.

- [ ] **Step 7: Commit**
```bash
git add web
git commit -m "feat: add dashboard with live agent feed and approval cards"
```

---

### Task 12: README writeup, LICENSE & submission assets (D)

**Files:**
- Create: `LICENSE`
- Modify (overwrite): `README.md`

- [ ] **Step 1: Write** `LICENSE` — the standard MIT License text, first line `MIT License`, then `Copyright (c) 2026 Cloud Cost Janitor contributors`, then the full MIT permission and warranty paragraphs (copy verbatim from https://opensource.org/license/mit).

- [ ] **Step 2: Write** `README.md` (this is the submission writeup):
````markdown
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
5. IAM: the `cost-janitor` user may only delete resources tagged `janitor-demo=true`. IAM does **not** block prod; layer 3 does.

## Architecture
```
React (5173) → FastAPI bridge (8080) → trueforge-sdk → TrueForge (8790) → OpenAI · Daytona sandbox · MCP aws-janitor (8000) → AWS
```

## How TrueForge is used
- **Agent loop & model:** the `cloud-cost-janitor` agent (spec in `agent/`) runs on TrueForge with an OpenAI model, registered by `scripts/bootstrap_trueforge.py` via TrueForge's HTTP API.
- **Tools:** our MCP server is attached as a remote connector; TrueForge calls the tools.
- **Sandbox:** the agent writes and runs Python in TrueForge's Daytona sandbox to rank costs and produce `teardown-plan.md` / `.csv`.
- **Human checkpoints:** TrueForge emits `tool.approval_required`; our bridge resumes the turn with `user.tool_approval` allow/deny decisions from the dashboard. The same agent also works in TrueForge's own chat UI.

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

## Run it (≈10 minutes)
Prereqs: Node ≥ 22.14, Python ≥ 3.11, an AWS account with a default VPC, an OpenAI key, a Daytona key (Sandboxes + Snapshots write).
```bash
cp .env.example .env                                  # fill in keys
python -m venv .venv
source .venv/Scripts/activate                         # Git Bash · PowerShell: .venv\Scripts\Activate.ps1 · macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
npx @truefoundry/trueforge@latest                      # terminal 1 → http://localhost:8790
python -m mcp_server.server                            # terminal 2 → http://localhost:8000/mcp
python -m scripts.bootstrap_trueforge                  # registers model, MCP server, sandbox, agent
python -m scripts.seed_aws                             # creates tagged demo waste (a few minutes)
uvicorn api.main:app --port 8080                       # terminal 3
cd web && npm install && npm run dev                   # terminal 4 → http://localhost:5173
```
Click **Run janitor** → watch the steps → approve / deny → read the report. Or open http://localhost:8790,
pick the `cloud-cost-janitor` agent, and ask it to clean up us-east-1.
Afterwards: `python -m scripts.cleanup_aws`.

Tests (no AWS needed): `pytest` and `cd web && npm test`.

## AI assistants used
Claude Code (Anthropic) helped with planning and implementation. The team reviewed every line and can walk through the architecture.

## Next steps
Multi-region fan-out, Cost Explorer-backed pricing, weekly runs via TrueForge Schedules, Slack approvals.
````

- [ ] **Step 3: Secrets check**

Run: `git ls-files | grep -E "^\.env$" ; git grep -nE "sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}" || echo clean`
Expected: no `.env` listed, prints `clean`.

- [ ] **Step 4: Commit**
```bash
git add README.md LICENSE
git commit -m "docs: add submission writeup and MIT license"
```

---

### Task 13: End-to-end integration & demo (everyone, 16:00)

**Files:** none new (fixes go back into the owning task's files with their tests)

- [ ] **Step 1: Full stack up** — 4 terminals as in README; `curl localhost:8080/api/health` → `{"trueforge": true, "mcp": true}`.
- [ ] **Step 2: Fresh seed** — `python -m scripts.cleanup_aws && python -m scripts.seed_aws`.
- [ ] **Step 2b: Cut-line fallback (only if the dashboard isn't integrated by 15:30).** Skip Steps 3–4 and run the same flow in TrueForge's UI at http://localhost:8790 with the `cloud-cost-janitor` agent: ask "Run the cost cleanup for us-east-1" → show a sandbox step and the plan file → Allow one delete → Deny one with a reason. Then continue at Step 5, using the TrueForge-only demo script in Step 6.
- [ ] **Step 3: Run from the UI.** Expected in order: list steps → `estimate_monthly_cost` → sandbox steps (violet) → blast-radius results (prod decoy shows red) → approval panel with ≥ 4 cards with $/mo and "safe".
- [ ] **Step 4: Decide** — approve all except the EIP; deny it with reason "reserved for tomorrow's launch". Submit.
Expected: status → running → done; report table shows deleted/denied/skipped-unsafe; audit trail lists both decisions; AWS console confirms the approved volumes are gone and the EIP + prod decoy remain. If approvals arrive one call at a time, decide each card as it appears — same result, more rounds.
If an approved ALB delete returns `AccessDenied`, change `scripts/iam-policy.json` so `elasticloadbalancing:DeleteLoadBalancer` sits in its own statement with condition key `elasticloadbalancing:ResourceTag/janitor-demo` (keep the tag check), update the IAM user, and retry.
- [ ] **Step 5: Verify pytest + web tests still green** — `pytest && (cd web && npm test)`.
- [ ] **Step 6: Demo scripts.**
  - **Recorded video — hard cap 3:00, ≥ 30 s in TrueForge's own UI:**
    0:00–0:20 problem + $ waste number · 0:20–0:50 **TrueForge UI (:8790)**: the `cloud-cost-janitor` agent's Overview (delete tools shielded) and one session paused on Allow/Deny · 0:50–1:40 dashboard run: MCP tool steps, open a sandbox step to show the generated Python, prod decoy marked unsafe · 1:40–2:25 **the gate**: read one card (cost, blast radius), approve some, deny the EIP with a reason · 2:25–2:50 report + audit trail + AWS console showing what's gone and what's kept · 2:50–3:00 safety layers in one line.
  - **Live demo — ≤ 5:00:** same order, with time for the safety layers (annotation gate, name gate, demo-tag rail, in-tool prod refusal, DryRun, IAM condition) and one architecture sentence per layer.
  - **TrueForge-only variant (cut-line fallback):** replace the dashboard segments with the same actions in TrueForge's chat UI; keep the timings.
- [ ] **Step 7: Record the video** per the 3:00 script (no keys on screen). Check length ≤ 3:00 before uploading. Re-seed for the live demo.
- [ ] **Step 8: Push & submit** (after team OK):
```bash
git push origin main
```
Post the build story on LinkedIn/X tagging @truefoundry and @polariscodes (community prize).
