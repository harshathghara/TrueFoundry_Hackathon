import pytest
from botocore.exceptions import ClientError
from conftest import REGION

import scripts.cleanup_aws as cleanup_aws
from mcp_server import aws_scan
from scripts.cleanup_aws import cleanup, delete_target_group_with_retry
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


def test_seed_is_rerunnable(aws, ami_id):
    first = seed(REGION, ami_id=ami_id)
    second = seed(REGION, ami_id=ami_id)
    assert first["load_balancer"] != second["load_balancer"]


class _FakeElbv2ResourceInUseThenOk:
    """Fake elbv2 client: delete_target_group raises ResourceInUse twice, then succeeds."""

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    def delete_target_group(self, TargetGroupArn):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ClientError({"Error": {"Code": "ResourceInUse", "Message": "in use"}}, "DeleteTargetGroup")
        return {}


class _FakeElbv2OtherError:
    """Fake elbv2 client: delete_target_group always raises a non-ResourceInUse error."""

    def __init__(self):
        self.calls = 0

    def delete_target_group(self, TargetGroupArn):
        self.calls += 1
        raise ClientError({"Error": {"Code": "SomeOtherError", "Message": "boom"}}, "DeleteTargetGroup")


def test_delete_target_group_with_retry_succeeds_after_resource_in_use(monkeypatch):
    sleeps = []
    monkeypatch.setattr(cleanup_aws, "_sleep", lambda seconds: sleeps.append(seconds))
    fake_elb = _FakeElbv2ResourceInUseThenOk(fail_times=2)

    delete_target_group_with_retry(fake_elb, "arn:demo-tg")

    assert fake_elb.calls == 3
    assert len(sleeps) == 2


def test_delete_target_group_with_retry_raises_other_errors_immediately(monkeypatch):
    sleeps = []
    monkeypatch.setattr(cleanup_aws, "_sleep", lambda seconds: sleeps.append(seconds))
    fake_elb = _FakeElbv2OtherError()

    with pytest.raises(ClientError):
        delete_target_group_with_retry(fake_elb, "arn:demo-tg")

    assert fake_elb.calls == 1
    assert sleeps == []
