"""IsolateStage — runs swap tests from a named isolation design."""

from __future__ import annotations

from thesean.models import SwapTestSpec
from thesean.models.comparison import ComparisonReport
from thesean.models.isolation import IsolationResultBundle
from thesean.pipeline.context import RunContext
from thesean.pipeline.state import StageResult


def _isolate_output_is_valid(ctx: RunContext) -> bool:
    path = ctx.output_path("isolate")
    if not path.exists():
        return False
    try:
        IsolationResultBundle.model_validate_json(path.read_text())
        return True
    except Exception:
        return False


class IsolateStage:
    name = "isolate"
    requires = ("compare",)

    def is_up_to_date(self, ctx: RunContext) -> bool:
        return _isolate_output_is_valid(ctx)

    def run(self, ctx: RunContext) -> StageResult:
        from thesean.pipeline.isolation import build_isolation_plan
        from thesean.pipeline.isolation.executor import execute_swap_test

        report = ComparisonReport.model_validate_json(
            (ctx.stage_output_dir / "compare_report.json").read_text()
        )
        regressions = [m for m in report.metrics if m.status == "regression"]

        plan = build_isolation_plan("screening_v1")

        if not regressions:
            bundle = IsolationResultBundle(
                design=plan.design,
                cases=plan.cases,
                swap_results=[],
            )
            output = ctx.output_path("isolate")
            output.write_text(bundle.model_dump_json(indent=2))
            return StageResult(
                primary_output=str(output),
                output_paths=[str(output)],
                summary="No regressions — no swap tests run",
                metadata={"num_swap_tests": 0, "skipped_reason": "no_regressions"},
            )

        swap_dir = ctx.workspace / "swap_results"
        swap_dir.mkdir(parents=True, exist_ok=True)

        swap_results = []
        warnings: list[str] = []
        for case in plan.cases:
            spec = SwapTestSpec(test_id=case.test_id, factors=case.factors)
            result = execute_swap_test(
                spec,
                ctx.baseline_manifest,
                ctx.candidate_manifest,
                ctx.factory,
            )
            swap_results.append(result)
            (swap_dir / f"{case.test_id}.json").write_text(result.model_dump_json(indent=2))
            if result.status == "failed":
                warnings.append(f"Swap test {case.test_id} failed: {result.error}")

        bundle = IsolationResultBundle(
            design=plan.design,
            cases=plan.cases,
            swap_results=swap_results,
        )
        output = ctx.output_path("isolate")
        output.write_text(bundle.model_dump_json(indent=2))

        return StageResult(
            primary_output=str(output),
            output_paths=[str(output)] + [str(swap_dir / f"{c.test_id}.json") for c in plan.cases],
            summary=f"{len(swap_results)} swap tests completed",
            warnings=warnings,
            metadata={"num_swap_tests": len(swap_results)},
        )
