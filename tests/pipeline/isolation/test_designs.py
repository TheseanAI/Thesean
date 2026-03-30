"""Tests for named isolation designs."""

from __future__ import annotations

import pytest

from thesean.pipeline.isolation import build_isolation_plan
from thesean.pipeline.isolation.designs import screening_v1


class TestScreeningV1:
    def test_returns_6_cases(self) -> None:
        plan = screening_v1()
        assert len(plan.cases) == 6

    def test_design_name(self) -> None:
        plan = screening_v1()
        assert plan.design == "screening_v1"

    def test_exact_case_ids(self) -> None:
        plan = screening_v1()
        ids = [c.test_id for c in plan.cases]
        assert ids == [
            "baseline",
            "candidate",
            "swap_wm",
            "swap_planner",
            "swap_env",
            "swap_wm_planner",
        ]

    def test_baseline_case_all_baseline(self) -> None:
        plan = screening_v1()
        baseline = plan.cases[0]
        assert baseline.factors.world_model == "baseline"
        assert baseline.factors.planner == "baseline"
        assert baseline.factors.env == "baseline"

    def test_candidate_case_all_candidate(self) -> None:
        plan = screening_v1()
        candidate = plan.cases[1]
        assert candidate.factors.world_model == "candidate"
        assert candidate.factors.planner == "candidate"
        assert candidate.factors.env == "candidate"


class TestBuildIsolationPlan:
    def test_screening_v1(self) -> None:
        plan = build_isolation_plan("screening_v1")
        assert plan.design == "screening_v1"
        assert len(plan.cases) == 6

    def test_unknown_design_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown isolation design: bogus"):
            build_isolation_plan("bogus")
