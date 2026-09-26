from pathlib import Path

INSTRUCTIONS = (Path(__file__).parent.parent / "agent" / "instructions.md").read_text(encoding="utf-8")


def test_instructions_cover_reporting_and_ordering_requirements():
    assert "Savings achieved" in INSTRUCTIONS
    assert "Annualized" in INSTRUCTIONS
    assert "descending" in INSTRUCTIONS
