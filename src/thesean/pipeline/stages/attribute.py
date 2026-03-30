"""AttributeStage — computes attribution from compare metrics + isolate swap results."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from thesean.models.comparison import ComparisonReport
from thesean.models.isolation import AttributionTable, IsolationResultBundle
from thesean.pipeline.context import RunContext
from thesean.pipeline.state import StageResult

_ATTR_TABLES = TypeAdapter(list[AttributionTable])


def _attribute_output_is_valid(ctx: RunContext) -> bool:
    path = ctx.output_path("attribute")
    if not path.exists():
        return False
    try:
        _ATTR_TABLES.validate_json(path.read_text())
        return True
    except Exception:
        return False


class AttributeStage:
    name = "attribute"
    requires = ("compare", "isolate")

    def is_up_to_date(self, ctx: RunContext) -> bool:
        return _attribute_output_is_valid(ctx)

    def run(self, ctx: RunContext) -> StageResult:
        from thesean.pipeline.isolation.attribution import compute_attribution

        report = ComparisonReport.model_validate_json(
            (ctx.stage_output_dir / "compare_report.json").read_text()
        )
        regressions = [m for m in report.metrics if m.status == "regression"]

        if not regressions:
            output = ctx.output_path("attribute")
            output.write_text("[]")
            return StageResult(
                primary_output=str(output),
                output_paths=[str(output)],
                summary="No regressions — no attributions computed",
                metadata={"num_attributions": 0, "skipped_reason": "no_regressions"},
            )

        # Read structured isolate bundle
        bundle = IsolationResultBundle.model_validate_json(
            ctx.output_path("isolate").read_text()
        )
        swap_results = bundle.swap_results

        tables: list[AttributionTable] = []
        warnings: list[str] = []

        for metric in regressions:
            table = compute_attribution(metric, swap_results)
            tables.append(table)
            if table.decision == "not_attributable":
                warnings.append(f"{metric.metric_id} not attributable")

        # Typed stage output: list[AttributionTable]
        output = ctx.output_path("attribute")
        output.write_text(json.dumps([t.model_dump() for t in tables], indent=2))

        return StageResult(
            primary_output=str(output),
            output_paths=[str(output)],
            summary=f"{len(tables)} attributions computed",
            warnings=warnings,
            metadata={"num_attributions": len(tables)},
        )
