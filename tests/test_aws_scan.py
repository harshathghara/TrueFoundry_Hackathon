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
