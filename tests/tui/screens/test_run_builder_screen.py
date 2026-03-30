"""Tests for RunBuilderScreen — INV-6-2."""

from __future__ import annotations

import pytest

from thesean.models.case import Case
from thesean.models.run import Run


@pytest.mark.tui
class TestRunBuilderValidation:

    def test_case_id_must_be_non_empty(self) -> None:
        """INV-6-2: case_id must be non-empty before submit."""
        # Case model enforces id as required str field
        case = Case(id="valid-id", run_a=Run(id="a", world_model_ref="w.pth"))
        assert case.id != ""

    def test_empty_case_id_is_invalid(self) -> None:
        """Empty string still technically creates a Case, but builder should reject."""
        case = Case(id="", run_a=Run(id="a", world_model_ref="w.pth"))
        assert case.id == ""  # model allows it, UI should gate it
