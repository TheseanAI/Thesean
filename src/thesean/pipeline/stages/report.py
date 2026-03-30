"""ReportStage — generates summary, HTML report, evidence pack, console output."""

from __future__ import annotations

from pathlib import Path

from thesean.models.evidence import EvidencePack
from thesean.pipeline.context import RunContext
from thesean.pipeline.state import StageResult
from thesean.reporting.types import ReportBundle


def _report_outputs_are_valid(workspace: Path) -> bool:
    summary_path = workspace / "summary.json"
    html_path = workspace / "report.html"
    evidence_path = workspace / "evidence_pack.json"

    if not (summary_path.exists() and html_path.exists() and evidence_path.exists()):
        return False
    try:
        ReportBundle.model_validate_json(summary_path.read_text())
        EvidencePack.model_validate_json(evidence_path.read_text())
        return True
    except Exception:
        return False


class ReportStage:
    name = "report"
    requires = ("compare",)

    def is_up_to_date(self, ctx: RunContext) -> bool:
        return _report_outputs_are_valid(ctx.workspace)

    def run(self, ctx: RunContext) -> StageResult:
        from thesean.reporting.bundle import build_report_bundle
        from thesean.reporting.evidence import materialize_evidence_pack_from_bundle
        from thesean.reporting.renderers.console import print_console_bundle
        from thesean.reporting.renderers.html import write_html_bundle
        from thesean.reporting.renderers.json import write_json_bundle

        bundle = build_report_bundle(ctx.workspace)

        write_json_bundle(bundle, ctx.workspace)
        write_html_bundle(bundle, ctx.workspace)
        print_console_bundle(bundle)

        pack = materialize_evidence_pack_from_bundle(bundle)
        evidence_path = ctx.workspace / "evidence_pack.json"
        evidence_path.write_text(pack.model_dump_json(indent=2))

        summary_path = ctx.workspace / "summary.json"
        report_path = ctx.workspace / "report.html"

        return StageResult(
            primary_output=str(summary_path),
            output_paths=[str(summary_path), str(report_path), str(evidence_path)],
            summary=pack.summary,
        )
