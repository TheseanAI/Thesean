"""Tests for build_report_bundle() — loading typed stage outputs into ReportBundle."""

from __future__ import annotations

import json
from pathlib import Path

from thesean.models import RunManifest
from thesean.models.case import Case
from thesean.models.comparison import ComparisonReport, MetricComparison
from thesean.models.isolation import (
    AttributionTable,
    EffectEstimate,
    IsolationCase,
    IsolationResultBundle,
)
from thesean.models.run import Run
from thesean.models.swap import SwapFactors
from thesean.reporting.bundle import build_report_bundle


def _make_manifest(run_id: str = "run_1") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        world_model_weights="weights.pt",
        planner_config={},
        env_config={},
    )


def _make_compare_report() -> ComparisonReport:
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
            MetricComparison(
                metric_id="offtrack",
                baseline_value=0.1,
                candidate_value=0.1,
                delta=0.0,
                delta_badness=0.0,
                higher_is_better=False,
                status="no_change",
            ),
        ],
    )


def _setup_workspace(tmp_path: Path, *, include_isolation: bool = False, include_attribution: bool = False) -> Path:
    ws = tmp_path
    stage_dir = ws / "stage_outputs"
    stage_dir.mkdir()

    # Manifests
    (ws / "baseline_manifest.json").write_text(_make_manifest("baseline").model_dump_json())
    (ws / "candidate_manifest.json").write_text(_make_manifest("candidate").model_dump_json())

    # case.json — required by build_report_bundle
    case = Case(
        id="test-case",
        run_a=Run(id="baseline", world_model_ref="weights.pt"),
        run_b=Run(id="candidate", world_model_ref="weights.pt"),
    )
    (ws / "case.json").write_text(case.model_dump_json(indent=2))

    # Compare report (required)
    (stage_dir / "compare_report.json").write_text(_make_compare_report().model_dump_json())

    if include_isolation:
        bundle = IsolationResultBundle(
            design="screening_v1",
            cases=[
                IsolationCase(
                    test_id="baseline",
                    factors=SwapFactors(world_model="baseline", planner="baseline", env="baseline"),
                ),
            ],
            swap_results=[],
        )
        (stage_dir / "isolate.json").write_text(bundle.model_dump_json())

    if include_attribution:
        tables = [
            AttributionTable(
                metric_id="track_progress",
                main_effects=[EffectEstimate(factor="world_model", effect=0.05, confidence=1.0)],
                interaction_effects=[],
                decision="world_model",
            ),
        ]
        (stage_dir / "attribute.json").write_text(json.dumps([t.model_dump() for t in tables]))

    return ws


class TestBuildReportBundle:
    def test_loads_compare_and_manifests(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path)
        bundle = build_report_bundle(ws)
        assert bundle.baseline_manifest.run_id == "baseline"
        assert bundle.candidate_manifest.run_id == "candidate"
        assert len(bundle.compare.metrics) == 3

    def test_summary_counts(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path)
        bundle = build_report_bundle(ws)
        assert bundle.summary.total_metrics == 3
        assert bundle.summary.regressions == 1
        assert bundle.summary.improvements == 1
        assert bundle.summary.no_change == 1

    def test_isolation_absent(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path, include_isolation=False)
        bundle = build_report_bundle(ws)
        assert bundle.isolation is None

    def test_isolation_present(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path, include_isolation=True)
        bundle = build_report_bundle(ws)
        assert bundle.isolation is not None
        assert bundle.isolation.design == "screening_v1"
        assert len(bundle.isolation.cases) == 1

    def test_attribution_absent(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path, include_attribution=False)
        bundle = build_report_bundle(ws)
        assert bundle.attribution == []

    def test_attribution_present(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path, include_attribution=True)
        bundle = build_report_bundle(ws)
        assert len(bundle.attribution) == 1
        assert bundle.attribution[0].metric_id == "track_progress"
        assert bundle.attribution[0].decision == "world_model"

    def test_artifact_refs_compare_only(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path)
        bundle = build_report_bundle(ws)
        kinds = [a.kind for a in bundle.artifacts]
        assert "compare" in kinds
        assert "isolate" not in kinds
        assert "attribute" not in kinds

    def test_artifact_refs_all(self, tmp_path: Path) -> None:
        ws = _setup_workspace(tmp_path, include_isolation=True, include_attribution=True)
        bundle = build_report_bundle(ws)
        kinds = [a.kind for a in bundle.artifacts]
        assert "compare" in kinds
        assert "isolate" in kinds
        assert "attribute" in kinds

    def test_evidence_pack_uses_typed_attributions(self, tmp_path: Path) -> None:
        from thesean.reporting.evidence import materialize_evidence_pack_from_bundle

        ws = _setup_workspace(tmp_path, include_attribution=True)
        bundle = build_report_bundle(ws)
        pack = materialize_evidence_pack_from_bundle(bundle)
        assert isinstance(pack.attributions, list)
        assert len(pack.attributions) == 1
        assert pack.attributions[0].metric_id == "track_progress"
