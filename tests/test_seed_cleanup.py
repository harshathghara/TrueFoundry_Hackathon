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


def test_seed_is_rerunnable(aws, ami_id):
    first = seed(REGION, ami_id=ami_id)
    second = seed(REGION, ami_id=ami_id)
    assert first["load_balancer"] != second["load_balancer"]
