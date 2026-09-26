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
