"""Case serialization — read/write case.json alongside thesean.toml."""

from __future__ import annotations

from pathlib import Path

from thesean.models.case import Case


def save_case(case: Case, workspace: Path) -> Path:
    """Write case.json to workspace directory."""
    case_path = workspace / "case.json"
    case_path.write_text(case.model_dump_json(indent=2))
    return case_path


def load_case(workspace: Path) -> Case | None:
    """Load case.json from workspace directory, if it exists."""
    case_path = workspace / "case.json"
    if not case_path.exists():
        return None
    return Case.model_validate_json(case_path.read_text())
