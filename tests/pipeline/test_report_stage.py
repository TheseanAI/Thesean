"""Tests for ReportStage.is_up_to_date() shape validation.

Proves that stale pre-Phase-6 report artifacts are not reused on --resume.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from thesean.models import RunManifest
from thesean.models.comparison import ComparisonReport, MetricComparison
from thesean.pipeline.stages.report import ReportStage, _report_outputs_are_valid
from thesean.reporting.evidence import materialize_evidence_pack_from_bundle
from thesean.reporting.types import ReportBundle, ReportSummary


def _make_manifest(run_id: str = "run_1") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        world_model_weights="weights.pt",
        planner_config={},
        env_config={},
    )


def _make_compare() -> ComparisonReport:
    return ComparisonReport(
        baseline_run_dir="/tmp/b",
        candidate_run_dir="/tmp/c",
        metrics=[
            MetricComparison(
                metric_id="m1",
                baseline_value=0.8,
                candidate_value=0.7,
                delta=-0.1,
                delta_badness=0.1,
                higher_is_better=True,
                status="regression",
            ),
        ],
    )


def _make_valid_bundle(workspace: str = "/tmp/ws") -> ReportBundle:
    return ReportBundle(
        workspace=workspace,
        baseline_manifest=_make_manifest("baseline"),
        candidate_manifest=_make_manifest("candidate"),
        summary=ReportSummary(total_metrics=1, regressions=1, improvements=0, no_change=0),
        compare=_make_compare(),
    )


def _write_valid_phase6_outputs(ws: Path) -> None:
    """Write valid Phase 6 summary.json, evidence_pack.json, and report.html."""
    bundle = _make_valid_bundle(str(ws))
    (ws / "summary.json").write_text(bundle.model_dump_json(indent=2))

    pack = materialize_evidence_pack_from_bundle(bundle)
    (ws / "evidence_pack.json").write_text(pack.model_dump_json(indent=2))

    (ws / "report.html").write_text("<html>report</html>")


class TestReportOutputsAreValid:
    def test_false_when_summary_missing(self, tmp_path: Path) -> None:
        (tmp_path / "evidence_pack.json").write_text("{}")
        (tmp_path / "report.html").write_text("<html></html>")
        assert _report_outputs_are_valid(tmp_path) is False

    def test_false_when_evidence_missing(self, tmp_path: Path) -> None:
        bundle = _make_valid_bundle(str(tmp_path))
        (tmp_path / "summary.json").write_text(bundle.model_dump_json())
        (tmp_path / "report.html").write_text("<html></html>")
        assert _report_outputs_are_valid(tmp_path) is False

    def test_false_when_html_missing(self, tmp_path: Path) -> None:
        bundle = _make_valid_bundle(str(tmp_path))
        (tmp_path / "summary.json").write_text(bundle.model_dump_json())
        pack = materialize_evidence_pack_from_bundle(bundle)
        (tmp_path / "evidence_pack.json").write_text(pack.model_dump_json())
        assert _report_outputs_are_valid(tmp_path) is False

    def test_false_when_summary_has_old_shape(self, tmp_path: Path) -> None:
        # Pre-Phase-6 summary.json was an ad hoc dict, not a ReportBundle
        old_summary = {
            "baseline_manifest": {"run_id": "x"},
            "findings": [{"metric_id": "m1", "status": "regression"}],
        }
        (tmp_path / "summary.json").write_text(json.dumps(old_summary))
        pack = materialize_evidence_pack_from_bundle(_make_valid_bundle(str(tmp_path)))
        (tmp_path / "evidence_pack.json").write_text(pack.model_dump_json())
        (tmp_path / "report.html").write_text("<html></html>")
        assert _report_outputs_are_valid(tmp_path) is False

    def test_false_when_evidence_has_old_shape(self, tmp_path: Path) -> None:
        # Pre-Phase-6 evidence_pack.json had findings/swap_results/attributions as legacy types
        bundle = _make_valid_bundle(str(tmp_path))
        (tmp_path / "summary.json").write_text(bundle.model_dump_json())
        old_evidence = {
            "pack_id": "pack_abc12345",
            "created_at": "2026-01-01T00:00:00+00:00",
            "summary": "old",
            "baseline": {"run_id": "x", "world_model_weights": "w.pt", "planner_config": {}, "env_config": {}},
            "candidate": {"run_id": "y", "world_model_weights": "w.pt", "planner_config": {}, "env_config": {}},
            "findings": [],
            "swap_results": [],
            "attributions": [],
        }
        (tmp_path / "evidence_pack.json").write_text(json.dumps(old_evidence))
        (tmp_path / "report.html").write_text("<html></html>")
        assert _report_outputs_are_valid(tmp_path) is False

    def test_true_for_valid_phase6_outputs(self, tmp_path: Path) -> None:
        _write_valid_phase6_outputs(tmp_path)
        assert _report_outputs_are_valid(tmp_path) is True


class TestReportStageIsUpToDate:
    def test_delegates_to_validation(self, tmp_path: Path) -> None:
        _write_valid_phase6_outputs(tmp_path)
        ctx = MagicMock()
        ctx.workspace = tmp_path
        stage = ReportStage()
        assert stage.is_up_to_date(ctx) is True

    def test_rejects_stale_workspace(self, tmp_path: Path) -> None:
        # Empty workspace — no outputs at all
        ctx = MagicMock()
        ctx.workspace = tmp_path
        stage = ReportStage()
        assert stage.is_up_to_date(ctx) is False
