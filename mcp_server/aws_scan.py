"""Read-only discovery of idle AWS resources."""
import os
from datetime import datetime, timezone

import boto3


def tags_of(tag_list) -> dict:
    return {t["Key"]: t["Value"] for t in tag_list or []}


PROD_VALUES = {"prod", "production"}
PROD_KEYS = {"env", "environment"}


def is_prod_tagged(tags: dict) -> bool:
    lower = {k.lower(): v for k, v in tags.items() if isinstance(v, str)}
    return any(lower.get(k, "").lower() in PROD_VALUES for k in PROD_KEYS)


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
