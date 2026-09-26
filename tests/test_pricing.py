import pytest

from mcp_server.pricing import estimate, monthly_cost


def test_ebs_gp3_priced_per_gb():
    assert monthly_cost({"kind": "ebs", "size_gb": 100, "volume_type": "gp3"}, "us-east-1") == 8.0


def test_unknown_volume_type_falls_back_to_gp3():
    assert monthly_cost({"kind": "ebs", "size_gb": 10, "volume_type": "weird"}, "us-east-1") == 0.8


def test_stopped_instance_costs_its_volumes():
    r = {"kind": "ec2_stopped", "volumes": [{"kind": "ebs", "size_gb": 8, "volume_type": "gp2"}]}
    assert monthly_cost(r, "us-east-1") == 0.8


def test_eip_lb_snapshot():
    assert monthly_cost({"kind": "eip"}, "us-east-1") == 3.6
    assert monthly_cost({"kind": "lb", "lb_type": "application"}, "us-east-1") == 16.43
    assert monthly_cost({"kind": "snapshot", "size_gb": 20}, "us-east-1") == 1.0


def test_unknown_region_uses_default_prices():
    assert monthly_cost({"kind": "eip"}, "ap-south-1") == 3.6


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        monthly_cost({"kind": "rds"}, "us-east-1")


def test_estimate_totals_and_annotates():
    out = estimate([{"id": "a", "kind": "eip"}, {"id": "b", "kind": "ebs", "size_gb": 10, "volume_type": "gp3"}], "us-east-1")
    assert out["total_monthly_cost"] == 4.4
    assert [i["monthly_cost"] for i in out["items"]] == [3.6, 0.8]
    assert out["items"][0]["id"] == "a"
