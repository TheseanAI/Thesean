"""CompareStage — runs baseline vs candidate comparison."""

from __future__ import annotations

from thesean.pipeline.compare import compare_manifests
from thesean.pipeline.context import RunContext
from thesean.pipeline.state import StageResult


class CompareStage:
    name = "compare"
    requires = ()

    def is_up_to_date(self, ctx: RunContext) -> bool:
        report_path = ctx.stage_output_dir / "compare_report.json"
        return report_path.exists()

    def run(self, ctx: RunContext) -> StageResult:
        report = compare_manifests(
            baseline_manifest=ctx.baseline_manifest,
            candidate_manifest=ctx.candidate_manifest,
            workspace=ctx.workspace,
            factory=ctx.factory,
            n_resamples=ctx.settings.run.bootstrap_resamples,
            alpha=ctx.settings.run.alpha,
        )

        report_path = ctx.stage_output_dir / "compare_report.json"
        report_path.write_text(report.model_dump_json(indent=2))

        regressions = [m for m in report.metrics if m.status == "regression"]
        return StageResult(
            primary_output=str(report_path),
            output_paths=[str(report_path)],
            summary=f"{len(report.metrics)} metrics compared, {len(regressions)} regressions",
            metadata={"num_metrics": len(report.metrics), "num_regressions": len(regressions)},
        )
