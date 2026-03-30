"""Render report.html from a ReportBundle."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from thesean.reporting.types import ReportBundle


def write_html_bundle(bundle: ReportBundle, workspace: Path) -> Path:
    template_dir = files("thesean.reporting") / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("report.html.j2")

    html = template.render(
        baseline_manifest=bundle.baseline_manifest,
        candidate_manifest=bundle.candidate_manifest,
        summary=bundle.summary,
        metrics=bundle.compare.metrics,
        attribution=bundle.attribution,
        artifacts=bundle.artifacts,
    )
    out = workspace / "report.html"
    out.write_text(html)
    return out
