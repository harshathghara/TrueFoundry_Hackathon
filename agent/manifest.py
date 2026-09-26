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
            # Turning this on lets the model pause with tool.response_required, which the
            # dashboard can't answer (only tool.approval_required renders as an approval
            # card) and /decisions 409s on. Disabled as a spec deviation (ruling: I-3).
            "ask_user_questions": {"enabled": False},
            "dynamic_sub_agents": {"enabled": False},
            "iteration_limit": 60,
        },
    }
