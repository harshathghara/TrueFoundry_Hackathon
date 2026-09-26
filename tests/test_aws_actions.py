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
