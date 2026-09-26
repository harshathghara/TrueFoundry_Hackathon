from pathlib import Path

from mcp_server.server import DESTRUCTIVE_TOOLS

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")


def build_agent_manifest(model_fqn: str) -> dict:
    return {
        "model": {"name": model_fqn, "params": {"temperature": 0.1}},
        "instructions": INSTRUCTIONS,
        "mcp_servers": [{
            "name": "aws-janitor",
            "enable_tools": ["@all"],
            "preload": True,
            # Annotation gate plus explicit names: defense in depth if annotations are ever dropped.
            "require_approval_for_tools": ["@destructive", *DESTRUCTIVE_TOOLS],
        }],
        "config": {
            "sandbox": {"enabled": True},
            "generative_ui": {"enabled": False},
            "ask_user_questions": {"enabled": True},
            "dynamic_sub_agents": {"enabled": False},
            "iteration_limit": 60,
        },
    }
