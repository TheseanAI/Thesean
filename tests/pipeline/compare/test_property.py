"""Hypothesis-based property tests for pipeline statistical functions."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from thesean.pipeline.compare.stats import adjust_pvalues, bootstrap_ci
from thesean.pipeline.compare_module import _compute_metric


@pytest.mark.unit
@given(
    baseline_value=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    candidate_value=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    threshold=st.floats(min_value=1e-9, max_value=10.0, allow_nan=False, allow_infinity=False),
    higher_is_better=st.booleans(),
)
def test_classify_metric_always_valid_status(
    baseline_value: float,
    candidate_value: float,
    threshold: float,
    higher_is_better: bool,
) -> None:
    result = _compute_metric(
        metric_id="test_metric",
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        higher_is_better=higher_is_better,
        threshold=threshold,
    )
    assert result.status in {"regression", "improvement", "no_change"}


@pytest.mark.unit
@given(
    values=st.lists(
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        min_size=2,
        max_size=20,
    ),
)
@settings(max_examples=20, deadline=30000)
def test_bootstrap_ci_lo_le_hi(values: list[float]) -> None:
    lo, hi = bootstrap_ci(values, values, n_resamples=200)
    # When all values are identical, scipy may return nan
    if math.isnan(lo) or math.isnan(hi):
        return
    assert lo <= hi, f"bootstrap_ci returned lo={lo} > hi={hi}"


@pytest.mark.unit
@given(
    pvals=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    ),
)
def test_adjust_pvalues_invariants(pvals: list[float]) -> None:
    adjusted = adjust_pvalues(pvals)
    assert len(adjusted) == len(pvals), "output length must match input length"
    for raw, adj in zip(pvals, adjusted, strict=False):
        assert 0.0 <= adj <= 1.0, f"adjusted p-value {adj} out of [0,1]"
        assert adj >= raw - 1e-12, f"adjusted {adj} < raw {raw}"
