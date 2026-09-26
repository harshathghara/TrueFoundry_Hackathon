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
    # moto 5.2.3 ignores DisableApiTermination passed to run_instances, but honors
    # it via modify_instance_attribute, so set it explicitly after launch.
    iid = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1)["Instances"][0]["InstanceId"]
    ec2.modify_instance_attribute(InstanceId=iid, DisableApiTermination={"Value": True})
    out = check_blast_radius(iid, REGION)
    assert out["safe"] is False and any("termination protection" in r for r in out["reasons"])


def test_unknown_prefix_is_unsafe():
    out = check_blast_radius("db-xyz", REGION)
    assert out["safe"] is False
