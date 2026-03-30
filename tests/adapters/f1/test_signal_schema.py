"""Tests for SignalSchema construction and group membership."""

from __future__ import annotations

import pytest

from thesean.core.signal_schema import SignalDef, SignalSchema


@pytest.mark.unit
class TestSignalSchema:

    def test_construction(self) -> None:
        sd = SignalDef(name="speed", label="Speed", delta_threshold=0.5)
        schema = SignalSchema(groups={"Core": [sd]}, group_order=["Core"])
        assert schema.signal_names() == ["speed"]

    def test_get_def_found(self) -> None:
        sd = SignalDef(name="speed", label="Speed")
        schema = SignalSchema(groups={"Core": [sd]}, group_order=["Core"])
        assert schema.get_def("speed") is sd

    def test_get_def_not_found(self) -> None:
        schema = SignalSchema(groups={}, group_order=[])
        assert schema.get_def("missing") is None

    def test_delta_threshold_default(self) -> None:
        schema = SignalSchema(groups={}, group_order=[])
        assert schema.delta_threshold("missing") == 0.1

    def test_delta_threshold_from_def(self) -> None:
        sd = SignalDef(name="brake", label="Brake", delta_threshold=0.05)
        schema = SignalSchema(groups={"Core": [sd]}, group_order=["Core"])
        assert schema.delta_threshold("brake") == 0.05

    def test_group_order_respected(self) -> None:
        sd1 = SignalDef(name="a", label="A")
        sd2 = SignalDef(name="b", label="B")
        schema = SignalSchema(
            groups={"Second": [sd2], "First": [sd1]},
            group_order=["First", "Second"],
        )
        assert schema.signal_names() == ["a", "b"]

    def test_multiple_signals_per_group(self) -> None:
        defs = [
            SignalDef(name="steering", label="Steering"),
            SignalDef(name="throttle", label="Throttle"),
            SignalDef(name="brake", label="Brake"),
        ]
        schema = SignalSchema(groups={"Core": defs}, group_order=["Core"])
        assert len(schema.signal_names()) == 3


@pytest.mark.unit
class TestSignalDef:

    def test_frozen(self) -> None:
        sd = SignalDef(name="speed", label="Speed")
        with pytest.raises(AttributeError):
            sd.name = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        sd = SignalDef(name="x", label="X")
        assert sd.format == ".3f"
        assert sd.delta_threshold == 0.1
