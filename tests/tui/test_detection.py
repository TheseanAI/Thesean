"""Tests for DetectedContext — edge cases."""

from __future__ import annotations

import pytest

from thesean.tui.detection import DetectedContext, detect_context


@pytest.mark.unit
class TestDetectedContextConstruction:

    def test_defaults(self) -> None:
        ctx = DetectedContext()
        assert ctx.case is None
        assert ctx.project_root is None
        assert ctx.cases == []
        assert ctx.adapter is None


@pytest.mark.unit
class TestDetectContextEdgeCases:

    def test_missing_dir_returns_empty(self, tmp_path) -> None:
        """Empty workspace with no markers."""
        empty = tmp_path / "empty"
        empty.mkdir()
        ctx = detect_context(empty)
        assert ctx.case is None

    def test_thesean_toml_detected_as_case(self, tmp_path) -> None:
        """Directory with thesean.toml is detected as a case."""
        ws = tmp_path / "case1"
        ws.mkdir()
        (ws / "thesean.toml").write_text("[adapter]\ntype = 'f1'\n")
        ctx = detect_context(ws)
        assert ctx.case == ws.resolve()

    def test_project_root_from_git(self, tmp_path) -> None:
        """Directory with .git is detected as project root."""
        (tmp_path / ".git").mkdir()
        ctx = detect_context(tmp_path)
        assert ctx.project_root == tmp_path.resolve()
