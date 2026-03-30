"""Tests for ReportBundle and ReportSummary schema validation."""

from __future__ import annotations

from thesean.models import RunManifest
from thesean.models.comparison import ComparisonReport, MetricComparison
from thesean.reporting.types import ArtifactRef, ReportBundle, ReportSummary


def _make_manifest(run_id: str = "run_1") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        world_model_weights="weights.pt",
        planner_config={},
        env_config={},
    )


def _make_compare() -> ComparisonReport:
    return ComparisonReport(
        baseline_run_dir="/tmp/baseline",
        candidate_run_dir="/tmp/candidate",
        metrics=[
            MetricComparison(
                metric_id="track_progress",
                baseline_value=0.8,
                candidate_value=0.7,
                delta=-0.1,
                delta_badness=0.1,
                higher_is_better=True,
                status="regression",
            ),
            MetricComparison(
                metric_id="reward",
                baseline_value=1.0,
                candidate_value=1.1,
                delta=0.1,
                delta_badness=-0.1,
                higher_is_better=True,
                status="improvement",
            ),
        ],
    )


class TestReportSummary:
    def test_validates(self) -> None:
        s = ReportSummary(total_metrics=3, regressions=1, improvements=1, no_change=1)
        assert s.total_metrics == 3
        assert s.regressions == 1

    def test_json_round_trip(self) -> None:
        s = ReportSummary(total_metrics=2, regressions=1, improvements=0, no_change=1)
        loaded = ReportSummary.model_validate_json(s.model_dump_json())
        assert loaded.total_metrics == 2


class TestReportBundle:
    def test_validates(self) -> None:
        bundle = ReportBundle(
            workspace="/tmp/ws",
            baseline_manifest=_make_manifest("baseline"),
            candidate_manifest=_make_manifest("candidate"),
            summary=ReportSummary(total_metrics=2, regressions=1, improvements=1, no_change=0),
            compare=_make_compare(),
        )
        assert bundle.workspace == "/tmp/ws"
        assert bundle.baseline_manifest.run_id == "baseline"
        assert bundle.candidate_manifest.run_id == "candidate"
        assert len(bundle.compare.metrics) == 2
        assert bundle.isolation is None
        assert bundle.attribution == []
        assert bundle.artifacts == []

    def test_json_round_trip(self) -> None:
        bundle = ReportBundle(
            workspace="/tmp/ws",
            baseline_manifest=_make_manifest("baseline"),
            candidate_manifest=_make_manifest("candidate"),
            summary=ReportSummary(total_metrics=1, regressions=0, improvements=0, no_change=1),
            compare=ComparisonReport(
                baseline_run_dir="/tmp/b",
                candidate_run_dir="/tmp/c",
                metrics=[
                    MetricComparison(
                        metric_id="m1",
                        baseline_value=0.5,
                        candidate_value=0.5,
                        delta=0.0,
                        delta_badness=0.0,
                        higher_is_better=True,
                        status="no_change",
                    ),
                ],
            ),
            artifacts=[ArtifactRef(kind="compare", label="Compare report", path="/tmp/x.json")],
        )
        json_str = bundle.model_dump_json()
        loaded = ReportBundle.model_validate_json(json_str)
        assert loaded.workspace == "/tmp/ws"
        assert len(loaded.compare.metrics) == 1
        assert loaded.compare.metrics[0].metric_id == "m1"
        assert len(loaded.artifacts) == 1
        assert loaded.artifacts[0].kind == "compare"

    def test_optional_fields_default(self) -> None:
        bundle = ReportBundle(
            workspace="/tmp/ws",
            baseline_manifest=_make_manifest(),
            candidate_manifest=_make_manifest(),
            summary=ReportSummary(total_metrics=0, regressions=0, improvements=0, no_change=0),
            compare=ComparisonReport(
                baseline_run_dir="/tmp/b",
                candidate_run_dir="/tmp/c",
                metrics=[],
            ),
        )
        assert bundle.isolation is None
        assert bundle.attribution == []
        assert bundle.artifacts == []
