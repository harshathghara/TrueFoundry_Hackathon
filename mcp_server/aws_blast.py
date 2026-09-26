"""Dependency checks run before proposing any deletion."""
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from mcp_server.aws_scan import is_prod_tagged, tags_of


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
    return ["tagged env=prod"] if is_prod_tagged(tags) else []


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
    warnings = [f"listener {l['Protocol']}:{l['Port']} still configured"
                for l in elb.describe_listeners(LoadBalancerArn=arn)["Listeners"]]
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
