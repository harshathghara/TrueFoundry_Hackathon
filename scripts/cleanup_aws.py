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
