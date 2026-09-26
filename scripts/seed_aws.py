"""Create tagged demo waste: 2 unattached volumes, 1 prod decoy, 1 stopped instance, 1 idle ALB, 1 EIP, 1 snapshot."""
import argparse
import json
import uuid

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

    suffix = uuid.uuid4().hex[:6]
    lb = elb.create_load_balancer(Name=f"janitor-demo-alb-{suffix}", Subnets=subnet_ids, Type="application", Scheme="internet-facing",
                                  Tags=[DEMO])["LoadBalancers"][0]
    tg = elb.create_target_group(Name=f"janitor-demo-tg-{suffix}", Protocol="HTTP", Port=80, VpcId=vpc, TargetType="instance",
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
