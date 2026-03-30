"""Tests for Phase 3: Adapter protocol compatibility."""

from __future__ import annotations

import pytest

pytest.importorskip("planner", reason="F1 adapter deps not available")

from thesean.adapters.f1.factory import F1AdapterFactory
from thesean.adapters.f1.signals import F1SignalTranslator
from thesean.core.contracts import SignalTranslator


class TestF1AdapterExtensions:
    def setup_method(self):
        self.factory = F1AdapterFactory()

    def test_has_detect_project(self):
        assert hasattr(self.factory, "detect_project")

    def test_has_get_signal_translator(self):
        translator = self.factory.get_signal_translator()
        assert translator is not None
        assert isinstance(translator, SignalTranslator)

    def test_has_get_panel_providers(self):
        providers = self.factory.get_panel_providers()
        assert isinstance(providers, list)

    def test_signal_translator_protocol(self):
        """F1SignalTranslator satisfies SignalTranslator protocol."""
        t = F1SignalTranslator()
        assert isinstance(t, SignalTranslator)
        assert len(t.signal_names()) > 0
        result = t.translate_step({"action": [0.1, 0.5, 0.0]})
        assert isinstance(result, dict)
