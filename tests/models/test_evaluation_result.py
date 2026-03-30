"""Tests for EvaluationResult model — INV-1 coverage."""

from __future__ import annotations

import pytest

from thesean.models.evaluation_result import ConfigSnapshot, EvaluationResult


@pytest.mark.unit
class TestConfigSnapshot:

    def test_roundtrip(self) -> None:
        snap = ConfigSnapshot(
            case_id="case-1",
            track_ref="monza",
            episode_count=5,
            run_a_world_model_ref="wm_a.pth",
            run_b_world_model_ref="wm_b.pth",
            adapter_name="f1",
        )
        restored = ConfigSnapshot.model_validate_json(snap.model_dump_json())
        assert restored == snap

    def test_defaults(self) -> None:
        snap = ConfigSnapshot(case_id="minimal")
        assert snap.track_ref == ""
        assert snap.episode_count == 0
        assert snap.eval_seeds is None
        assert snap.adapter_name == ""


@pytest.mark.unit
class TestEvaluationResult:

    def test_roundtrip(self) -> None:
        snap = ConfigSnapshot(case_id="c1")
        result = EvaluationResult(config=snap, episodes_a=[{"a": 1}], episodes_b=[{"b": 2}])
        restored = EvaluationResult.model_validate_json(result.model_dump_json())
        assert restored.config == snap
        assert restored.episodes_a == [{"a": 1}]
        assert restored.episodes_b == [{"b": 2}]

    def test_defaults(self) -> None:
        snap = ConfigSnapshot(case_id="c1")
        result = EvaluationResult(config=snap)
        assert result.schema_version == 1
        assert result.created_at  # should be auto-populated
        assert result.episodes_a == []
        assert result.episodes_b == []
        assert result.outcomes == {}
        assert result.events is None

    def test_schema_version(self) -> None:
        snap = ConfigSnapshot(case_id="c1")
        result = EvaluationResult(config=snap, schema_version=2)
        assert result.schema_version == 2
