from __future__ import annotations

from pydantic import BaseModel, Field

from thesean.models.swap import SwapFactors, SwapTestResult


class IsolationCase(BaseModel):
    test_id: str
    factors: SwapFactors


class IsolationPlan(BaseModel):
    design: str = "screening_v1"
    cases: list[IsolationCase] = Field(default_factory=list)


class IsolationResultBundle(BaseModel):
    design: str
    cases: list[IsolationCase] = Field(default_factory=list)
    swap_results: list[SwapTestResult] = Field(default_factory=list)


class EffectEstimate(BaseModel):
    factor: str
    effect: float
    confidence: float | None = None
    support_tests: list[str] = Field(default_factory=list)


class AttributionTable(BaseModel):
    metric_id: str
    main_effects: list[EffectEstimate] = Field(default_factory=list)
    interaction_effects: list[EffectEstimate] = Field(default_factory=list)
    decision: str
