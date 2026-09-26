import json
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parent.parent / "scripts" / "iam-policy.json"
DEMO_TAG_CONDITION = {"StringEquals": {"aws:ResourceTag/janitor-demo": "true"}}
DESTRUCTIVE_PREFIXES = ("Delete", "Terminate", "Release", "Stop")


def _action_name(action: str) -> str:
    return action.split(":", 1)[1]


def test_destructive_actions_are_all_tag_conditioned():
    policy = json.loads(POLICY_PATH.read_text())
    for statement in policy["Statement"]:
        actions = statement["Action"]
        if isinstance(actions, str):
            actions = [actions]
        destructive = [a for a in actions if _action_name(a).startswith(DESTRUCTIVE_PREFIXES)]
        if destructive:
            assert statement.get("Condition") == DEMO_TAG_CONDITION, (
                f"Statement {statement.get('Sid')} contains destructive actions {destructive} "
                f"without the janitor-demo tag condition"
            )


def test_create_tags_is_scoped_to_seed_created_resource_types():
    policy = json.loads(POLICY_PATH.read_text())
    create_tags_condition = {"StringEquals": {"ec2:CreateAction": ["CreateVolume", "RunInstances", "CreateSnapshot", "AllocateAddress"]}}
    for statement in policy["Statement"]:
        actions = statement["Action"]
        if isinstance(actions, str):
            actions = [actions]
        if "ec2:CreateTags" in actions:
            assert statement.get("Condition") == create_tags_condition, (
                f"Statement {statement.get('Sid')} grants ec2:CreateTags without the ec2:CreateAction condition"
            )
