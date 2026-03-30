"""Write summary.json from a ReportBundle."""

from __future__ import annotations

from pathlib import Path

from thesean.reporting.types import ReportBundle


def write_json_bundle(bundle: ReportBundle, workspace: Path) -> Path:
    out = workspace / "summary.json"
    out.write_text(bundle.model_dump_json(indent=2))
    return out
