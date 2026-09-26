"""Static AWS list prices (USD/month) used for demo cost estimates.

Cost Explorer lags ~24h and has no history for freshly created resources, so we price from a table.
"""

DEFAULT_REGION = "us-east-1"

PRICES = {
    "us-east-1": {
        "ebs_gb": {"gp3": 0.08, "gp2": 0.10, "io1": 0.125, "io2": 0.125, "st1": 0.045, "sc1": 0.015, "standard": 0.05},
        "snapshot_gb": 0.05,
        "eip": 3.60,
        "alb": 16.43,
        "nlb": 16.43,
    },
}


def _prices(region: str) -> dict:
    return PRICES.get(region, PRICES[DEFAULT_REGION])


def monthly_cost(resource: dict, region: str) -> float:
    p = _prices(region)
    kind = resource["kind"]
    if kind == "ebs":
        rate = p["ebs_gb"].get(resource.get("volume_type", "gp3"), p["ebs_gb"]["gp3"])
        return round(resource["size_gb"] * rate, 2)
    if kind == "snapshot":
        # Upper bound: snapshots are incremental, we price the full source volume size.
        return round(resource["size_gb"] * p["snapshot_gb"], 2)
    if kind == "eip":
        return p["eip"]
    if kind == "lb":
        return p["nlb"] if resource.get("lb_type") == "network" else p["alb"]
    if kind == "ec2_stopped":
        # A stopped instance has no compute charge but still pays for its EBS volumes.
        return round(sum(monthly_cost(v, region) for v in resource.get("volumes", [])), 2)
    raise ValueError(f"unknown resource kind: {kind}")


def estimate(resources: list[dict], region: str) -> dict:
    items = [{**r, "monthly_cost": monthly_cost(r, region)} for r in resources]
    return {
        "region": region,
        "items": items,
        "total_monthly_cost": round(sum(i["monthly_cost"] for i in items), 2),
    }
