from __future__ import annotations

from thesean.models.isolation import IsolationPlan
from thesean.pipeline.isolation.designs import screening_v1


def build_isolation_plan(design: str = "screening_v1") -> IsolationPlan:
    if design == "screening_v1":
        return screening_v1()
    raise ValueError(f"Unknown isolation design: {design}")
