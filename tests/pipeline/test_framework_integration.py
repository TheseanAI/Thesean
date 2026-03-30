"""Framework integration tests using DummyAdapterFactory.

Proves the full pipeline works without any real adapter.
"""

from __future__ import annotations

from pathlib import Path

from thesean.pipeline.context import RunContext
from thesean.pipeline.runner import run_stages
from thesean.pipeline.stages import (
    AttributeStage,
    CompareStage,
    IsolateStage,
    ReportStage,
)


class TestCompareStageWithDummy:
    def test_compare_produces_typed_artifact(self, dummy_workspace: Path) -> None:
        ctx = RunContext(dummy_workspace, pipeline_names=("compare",))
        run_stages(ctx, (CompareStage(),))

        report_path = dummy_workspace / "stage_outputs" / "compare_report.json"
        assert report_path.exists()

        from thesean.models.comparison import ComparisonReport

        report = ComparisonReport.model_validate_json(report_path.read_text())
        assert len(report.metrics) > 0


class TestFullPipelineWithDummy:
    def test_all_canonical_artifacts_produced(self, dummy_workspace: Path) -> None:
        ctx = RunContext(
            dummy_workspace,
            pipeline_names=("compare", "isolate", "attribute", "report"),
        )
        run_stages(
            ctx,
            (CompareStage(), IsolateStage(), AttributeStage(), ReportStage()),
        )

        assert (dummy_workspace / "stage_outputs" / "compare_report.json").exists()
        assert (dummy_workspace / "stage_outputs" / "isolate.json").exists()
        assert (dummy_workspace / "stage_outputs" / "attribute.json").exists()
        assert (dummy_workspace / "summary.json").exists()
        assert (dummy_workspace / "report.html").exists()
        assert (dummy_workspace / "evidence_pack.json").exists()


class TestResumeWithDummy:
    def test_resume_reuses_completed_stages(self, dummy_workspace: Path) -> None:
        # First run
        ctx = RunContext(
            dummy_workspace,
            pipeline_names=("compare", "isolate", "attribute", "report"),
        )
        run_stages(
            ctx,
            (CompareStage(), IsolateStage(), AttributeStage(), ReportStage()),
        )

        # Second run with resume
        ctx2 = RunContext(
            dummy_workspace,
            resume=True,
            pipeline_names=("compare", "isolate", "attribute", "report"),
        )
        run_stages(
            ctx2,
            (CompareStage(), IsolateStage(), AttributeStage(), ReportStage()),
        )

        # All stages should be completed with reused=True
        for name in ("compare", "isolate", "attribute", "report"):
            stage_state = ctx2.state.stages.get(name)
            assert stage_state is not None
            assert stage_state.status == "completed"
            assert stage_state.reused is True
