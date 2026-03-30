"""Tests for isolation schemas: IsolationPlan, IsolationResultBundle, AttributionTable."""

from __future__ import annotations

from thesean.models.isolation import (
    AttributionTable,
    EffectEstimate,
    IsolationCase,
    IsolationPlan,
    IsolationResultBundle,
)
from thesean.models.swap import SwapFactors, SwapTestResult


class TestIsolationPlan:
    def test_validates(self) -> None:
        plan = IsolationPlan(
            design="screening_v1",
            cases=[
                IsolationCase(
                    test_id="baseline",
                    factors=SwapFactors(world_model="baseline", planner="baseline", env="baseline"),
                ),
            ],
        )
        assert plan.design == "screening_v1"
        assert len(plan.cases) == 1

    def test_empty_cases(self) -> None:
        plan = IsolationPlan()
        assert plan.design == "screening_v1"
        assert plan.cases == []


class TestIsolationResultBundle:
    def test_validates(self) -> None:
        bundle = IsolationResultBundle(
            design="screening_v1",
            cases=[
                IsolationCase(
                    test_id="baseline",
                    factors=SwapFactors(world_model="baseline", planner="baseline", env="baseline"),
                ),
            ],
            swap_results=[
                SwapTestResult(test_id="baseline", status="ok", metrics=[]),
            ],
        )
        assert bundle.design == "screening_v1"
        assert len(bundle.cases) == 1
        assert len(bundle.swap_results) == 1

    def test_json_round_trip(self) -> None:
        bundle = IsolationResultBundle(
            design="screening_v1",
            cases=[],
            swap_results=[],
        )
        json_str = bundle.model_dump_json()
        loaded = IsolationResultBundle.model_validate_json(json_str)
        assert loaded.design == "screening_v1"
        assert loaded.cases == []
        assert loaded.swap_results == []

    def test_empty_defaults(self) -> None:
        bundle = IsolationResultBundle(design="screening_v1")
        assert bundle.cases == []
        assert bundle.swap_results == []


class TestAttributionTable:
    def test_validates(self) -> None:
        table = AttributionTable(
            metric_id="track_progress",
            main_effects=[
                EffectEstimate(factor="world_model", effect=0.05, confidence=1.0),
            ],
            interaction_effects=[],
            decision="world_model",
        )
        assert table.metric_id == "track_progress"
        assert len(table.main_effects) == 1
        assert table.decision == "world_model"

    def test_json_round_trip(self) -> None:
        table = AttributionTable(
            metric_id="reward",
            main_effects=[
                EffectEstimate(
                    factor="planner", effect=0.03, confidence=0.9,
                    support_tests=["swap_planner"],
                ),
            ],
            interaction_effects=[
                EffectEstimate(
                    factor="interaction", effect=0.01, confidence=0.8,
                    support_tests=["swap_wm_planner"],
                ),
            ],
            decision="planner",
        )
        json_str = table.model_dump_json()
        loaded = AttributionTable.model_validate_json(json_str)
        assert loaded.metric_id == "reward"
        assert len(loaded.main_effects) == 1
        assert loaded.main_effects[0].effect == 0.03
        assert loaded.main_effects[0].support_tests == ["swap_planner"]
        assert len(loaded.interaction_effects) == 1
        assert loaded.decision == "planner"

    def test_empty_effects(self) -> None:
        table = AttributionTable(
            metric_id="test",
            decision="unknown",
        )
        assert table.main_effects == []
        assert table.interaction_effects == []


class TestEffectEstimate:
    def test_optional_confidence(self) -> None:
        e = EffectEstimate(factor="world_model", effect=0.05)
        assert e.confidence is None
        assert e.support_tests == []

    def test_with_all_fields(self) -> None:
        e = EffectEstimate(
            factor="planner",
            effect=0.03,
            confidence=1.0,
            support_tests=["swap_planner"],
        )
        assert e.factor == "planner"
        assert e.effect == 0.03
        assert e.confidence == 1.0
