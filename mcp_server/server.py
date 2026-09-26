"""aws-janitor MCP server: exposes AWS cleanup as annotated MCP tools over streamable HTTP."""
import functools
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_server import aws_actions, aws_blast, aws_scan, pricing

load_dotenv()

DEFAULT_REGION = os.getenv("AWS_REGION", "us-east-1")
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

READ_TOOLS = ["list_unattached_volumes", "list_stopped_instances", "list_idle_load_balancers",
              "list_unassociated_eips", "list_old_snapshots", "estimate_monthly_cost", "check_blast_radius"]
WRITE_TOOLS = ["snapshot_volume"]
DESTRUCTIVE_TOOLS = ["delete_volume", "terminate_instance", "delete_load_balancer", "release_eip", "delete_snapshot"]

mcp = FastMCP("aws-janitor", host=os.getenv("MCP_HOST", "127.0.0.1"), port=int(os.getenv("MCP_PORT", "8000")))


def safe(fn):
    """Never let a raw exception reach the model; return a structured error instead."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — tool boundary
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return wrapper


@mcp.tool(annotations=READ)
@safe
def list_unattached_volumes(region: str = DEFAULT_REGION) -> dict:
    """EBS volumes in 'available' state (not attached to any instance)."""
    return {"region": region, "items": aws_scan.list_unattached_volumes(region)}


@mcp.tool(annotations=READ)
@safe
def list_stopped_instances(region: str = DEFAULT_REGION) -> dict:
    """EC2 instances in 'stopped' state, with the EBS volumes they still pay for."""
    return {"region": region, "items": aws_scan.list_stopped_instances(region)}


@mcp.tool(annotations=READ)
@safe
def list_idle_load_balancers(region: str = DEFAULT_REGION) -> dict:
    """Application/Network load balancers with zero registered targets."""
    return {"region": region, "items": aws_scan.list_idle_load_balancers(region)}


@mcp.tool(annotations=READ)
@safe
def list_unassociated_eips(region: str = DEFAULT_REGION) -> dict:
    """Elastic IPs not associated with any instance or network interface."""
    return {"region": region, "items": aws_scan.list_unassociated_eips(region)}


@mcp.tool(annotations=READ)
@safe
def list_old_snapshots(region: str = DEFAULT_REGION, older_than_days: int | None = None) -> dict:
    """Self-owned EBS snapshots older than N days (default from JANITOR_SNAPSHOT_MIN_AGE_DAYS). Excludes janitor backups."""
    return {"region": region, "items": aws_scan.list_old_snapshots(region, older_than_days)}


@mcp.tool(annotations=READ)
@safe
def estimate_monthly_cost(resources: list[dict], region: str = DEFAULT_REGION) -> dict:
    """Monthly USD cost per resource (pass items from the list_* tools unchanged) plus the total."""
    return pricing.estimate(resources, region)


@mcp.tool(annotations=READ)
@safe
def check_blast_radius(resource_id: str, region: str = DEFAULT_REGION) -> dict:
    """What would break if this resource were deleted. Only propose deletion when safe is true."""
    return aws_blast.check_blast_radius(resource_id, region)


@mcp.tool(annotations=WRITE)
@safe
def snapshot_volume(volume_id: str, region: str = DEFAULT_REGION) -> dict:
    """Create a backup snapshot of a volume before deleting it (reversible, additive)."""
    return aws_actions.snapshot_volume(volume_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def delete_volume(volume_id: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently delete an EBS volume. Irreversible."""
    return aws_actions.delete_volume(volume_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def terminate_instance(instance_id: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently terminate an EC2 instance. Irreversible."""
    return aws_actions.terminate_instance(instance_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def delete_load_balancer(arn: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently delete a load balancer by ARN. Irreversible."""
    return aws_actions.delete_load_balancer(arn, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def release_eip(allocation_id: str, region: str = DEFAULT_REGION) -> dict:
    """Release an Elastic IP. The address cannot be recovered."""
    return aws_actions.release_eip(allocation_id, region)


@mcp.tool(annotations=DESTRUCTIVE)
@safe
def delete_snapshot(snapshot_id: str, region: str = DEFAULT_REGION) -> dict:
    """Permanently delete an EBS snapshot. Irreversible."""
    return aws_actions.delete_snapshot(snapshot_id, region)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
