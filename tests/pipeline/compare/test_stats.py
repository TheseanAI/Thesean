"""Tests for compare stats: bootstrap CI, paired p-value, p-value adjustment."""

from __future__ import annotations

from thesean.pipeline.compare.stats import adjust_pvalues, bootstrap_ci, paired_pvalue


class TestBootstrapCI:
    def test_returns_float_tuple(self) -> None:
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidate = [1.5, 2.5, 3.5, 4.5, 5.5]
        lo, hi = bootstrap_ci(baseline, candidate)
        assert isinstance(lo, float)
        assert isinstance(hi, float)

    def test_ci_excludes_zero_for_clear_shift(self) -> None:
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        candidate = [12.0, 11.5, 14.0, 13.0, 16.0, 15.5, 18.0, 17.5, 20.0, 19.0]
        lo, hi = bootstrap_ci(baseline, candidate)
        assert lo > 0, f"CI low should be > 0 for clear shift, got {lo}"
        assert hi > lo

    def test_ci_includes_zero_for_no_shift(self) -> None:
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidate = [1.1, 1.9, 3.1, 3.9, 5.1]
        lo, hi = bootstrap_ci(baseline, candidate)
        assert lo <= hi, f"CI bounds inverted: lo={lo} > hi={hi}"
        assert lo <= 0, f"CI low bound should be <= 0 for no shift, got {lo}"
        assert hi >= 0, f"CI high bound should be >= 0 for no shift, got {hi}"


class TestPairedPvalue:
    def test_returns_float_in_unit_interval(self) -> None:
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidate = [1.5, 2.5, 3.5, 4.5, 5.5]
        p = paired_pvalue(baseline, candidate)
        assert isinstance(p, float)
        assert 0.0 <= p <= 1.0

    def test_significant_for_large_shift(self) -> None:
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        candidate = [11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0]
        p = paired_pvalue(baseline, candidate)
        assert p < 0.05

    def test_not_significant_for_no_shift(self) -> None:
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidate = [1.1, 1.9, 3.1, 3.9, 5.1]
        p = paired_pvalue(baseline, candidate)
        assert p > 0.05


class TestAdjustPvalues:
    def test_returns_same_length(self) -> None:
        pvals = [0.01, 0.03, 0.05, 0.10]
        adj = adjust_pvalues(pvals)
        assert len(adj) == len(pvals)

    def test_returns_floats(self) -> None:
        pvals = [0.01, 0.03, 0.05]
        adj = adjust_pvalues(pvals)
        for v in adj:
            assert isinstance(v, float)

    def test_adjusted_geq_raw(self) -> None:
        """Holm-adjusted p-values should be >= raw p-values."""
        pvals = [0.01, 0.02, 0.04]
        adj = adjust_pvalues(pvals)
        for raw, corrected in zip(pvals, adj, strict=False):
            assert corrected >= raw - 1e-10
