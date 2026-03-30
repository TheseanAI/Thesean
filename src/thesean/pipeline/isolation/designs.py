from __future__ import annotations

from thesean.models.isolation import IsolationCase, IsolationPlan
from thesean.models.swap import SwapFactors


def screening_v1() -> IsolationPlan:
    """The standard 6-case screening design: 3 main effects + 1 interaction term."""
    cases = [
        IsolationCase(
            test_id="baseline",
            factors=SwapFactors(world_model="baseline", planner="baseline", env="baseline"),
        ),
        IsolationCase(
            test_id="candidate",
            factors=SwapFactors(world_model="candidate", planner="candidate", env="candidate"),
        ),
        IsolationCase(
            test_id="swap_wm",
            factors=SwapFactors(world_model="candidate", planner="baseline", env="baseline"),
        ),
        IsolationCase(
            test_id="swap_planner",
            factors=SwapFactors(world_model="baseline", planner="candidate", env="baseline"),
        ),
        IsolationCase(
            test_id="swap_env",
            factors=SwapFactors(world_model="baseline", planner="baseline", env="candidate"),
        ),
        IsolationCase(
            test_id="swap_wm_planner",
            factors=SwapFactors(world_model="candidate", planner="candidate", env="baseline"),
        ),
    ]
    return IsolationPlan(design="screening_v1", cases=cases)
