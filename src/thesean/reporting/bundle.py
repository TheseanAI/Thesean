"""Build a ReportBundle from workspace artifacts and typed stage outputs."""

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from thesean.models.case import Case
from thesean.models.comparison import ComparisonReport
from thesean.models.isolation import AttributionTable, IsolationResultBundle
from thesean.reporting.types import ArtifactRef, ReportBundle, ReportSummary

_ATTR_TABLES = TypeAdapter(list[AttributionTable])


def build_report_bundle(workspace: Path) -> ReportBundle:
    workspace = workspace.expanduser().resolve()
    stage_dir = workspace / "stage_outputs"

    case_path = workspace / "case.json"
    compare_path = stage_dir / "compare_report.json"

    if not case_path.exists():
        raise FileNotFoundError("case.json not found — case may not be fully initialized")
    if not compare_path.exists():
        raise FileNotFoundError("Pipeline has not run yet")

    case = Case.model_validate_json(case_path.read_text())
    baseline_manifest = case.run_a.to_manifest()
    candidate_manifest = case.run_b.to_manifest() if case.run_b else case.run_a.to_manifest()
    compare = ComparisonReport.model_validate_json(compare_path.read_text())

    isolation = None
    isolate_path = stage_dir / "isolate.json"
    if isolate_path.exists():
        isolation = IsolationResultBundle.model_validate_json(isolate_path.read_text())

    attribution: list[AttributionTable] = []
    attribute_path = stage_dir / "attribute.json"
    if attribute_path.exists():
        attribution = _ATTR_TABLES.validate_json(attribute_path.read_text())

    regressions = sum(1 for m in compare.metrics if m.status == "regression")
    improvements = sum(1 for m in compare.metrics if m.status == "improvement")
    no_change = sum(1 for m in compare.metrics if m.status == "no_change")

    artifacts = [
        ArtifactRef(kind="compare", label="Compare report", path=str(stage_dir / "compare_report.json")),
    ]
    if isolation is not None:
        artifacts.append(
            ArtifactRef(kind="isolate", label="Isolation bundle", path=str(stage_dir / "isolate.json"))
        )
    if attribution:
        artifacts.append(
            ArtifactRef(kind="attribute", label="Attribution tables", path=str(stage_dir / "attribute.json"))
        )

    return ReportBundle(
        workspace=str(workspace),
        baseline_manifest=baseline_manifest,
        candidate_manifest=candidate_manifest,
        summary=ReportSummary(
            total_metrics=len(compare.metrics),
            regressions=regressions,
            improvements=improvements,
            no_change=no_change,
        ),
        compare=compare,
        isolation=isolation,
        attribution=attribution,
        artifacts=artifacts,
    )
