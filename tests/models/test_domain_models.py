"""Tests for Phase 1 domain models: Project, Run, Case, Event, Explanation, Signal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from thesean.models.case import Case
from thesean.models.event import Event
from thesean.models.explanation import Explanation
from thesean.models.manifest import RunManifest
from thesean.models.project import DiscoveredAssets, Project
from thesean.models.run import Run
from thesean.models.signal import SignalValue

# ── SignalValue ──────────────────────────────────────────────────────────

class TestSignalValue:
    def test_roundtrip(self):
        sv = SignalValue(name="speed", value=12.5, unit="m/s", display_format=".1f")
        raw = json.loads(sv.model_dump_json())
        sv2 = SignalValue.model_validate(raw)
        assert sv2 == sv

    def test_defaults(self):
        sv = SignalValue(name="x", value=0.0)
        assert sv.unit is None
        assert sv.display_format == ".3f"


# ── Project ──────────────────────────────────────────────────────────────

class TestProject:
    def test_roundtrip(self):
        p = Project(
            project_root=Path("/tmp/f1"),
            adapter_name="f1",
            discovered_assets=DiscoveredAssets(
                weights=[{"name": "wm_v1.pth", "path": "/tmp/f1/checkpoints/wm_v1.pth"}],
                envs=["silverstone", "monza"],
            ),
        )
        raw = json.loads(p.model_dump_json())
        p2 = Project.model_validate(raw)
        assert p2.adapter_name == "f1"
        assert len(p2.discovered_assets.weights) == 1
        assert p2.discovered_assets.envs == ["silverstone", "monza"]


# ── Run ──────────────────────────────────────────────────────────────────

class TestRun:
    def test_roundtrip(self):
        r = Run(
            id="run-a",
            world_model_ref="/weights/v12.pth",
            planner_ref="cem",
            planner_config={"horizon": 10},
            env_config={"track_csv": "tracks/silverstone.csv"},
            seed=42,
            num_episodes=20,
        )
        raw = json.loads(r.model_dump_json())
        r2 = Run.model_validate(raw)
        assert r2 == r

    def test_from_manifest(self):
        m = RunManifest(
            run_id="baseline",
            world_model_weights="/w/v1.pth",
            planner_config={"h": 10},
            env_config={"track": "s"},
            num_episodes=30,
            seed=7,
        )
        r = Run.from_manifest(m)
        assert r.id == "baseline"
        assert r.world_model_ref == "/w/v1.pth"
        assert r.seed == 7
        assert r.num_episodes == 30

    def test_to_manifest_roundtrip(self):
        m = RunManifest(
            run_id="x",
            world_model_weights="/w.pth",
            planner_config={"a": 1},
            env_config={"b": 2},
            num_episodes=10,
            seed=3,
        )
        r = Run.from_manifest(m)
        m2 = r.to_manifest()
        assert m2.run_id == m.run_id
        assert m2.world_model_weights == m.world_model_weights
        assert m2.seed == m.seed

    def test_manifest_to_run_method(self):
        m = RunManifest(
            run_id="test",
            world_model_weights="/w.pth",
            planner_config={},
            env_config={},
        )
        r = m.to_run()
        assert r.id == "test"
        assert isinstance(r, Run)


# ── Event ────────────────────────────────────────────────────────────────

class TestEvent:
    def test_roundtrip(self):
        e = Event(
            id="evt-001",
            type="first_signal_divergence",
            step=143,
            time_s=14.3,
            severity="critical",
            score=0.42,
            persistence_k=4,
            active_signals=[
                SignalValue(name="steering_delta", value=0.18),
                SignalValue(name="heading_delta", value=0.24),
            ],
            local_window=(140, 150),
        )
        raw = json.loads(e.model_dump_json())
        e2 = Event.model_validate(raw)
        assert e2.step == 143
        assert e2.type == "first_signal_divergence"
        assert len(e2.active_signals) == 2

    def test_enum_validation(self):
        with pytest.raises(ValidationError):
            Event(id="bad", type="not_a_valid_type", step=0)

    def test_defaults(self):
        e = Event(id="x", type="terminal", step=500)
        assert e.severity == "warning"
        assert e.score == 0.0
        assert e.active_signals == []


# ── Explanation ──────────────────────────────────────────────────────────

class TestExplanation:
    def test_roundtrip(self):
        ex = Explanation(
            id="expl-001",
            event_id="evt-001",
            label="WM-led onset + planner amplification",
            confidence=0.78,
            tier="tier_2",
            support_basis=["onset", "swap", "closed-loop"],
            competing=["interaction_effect", "planner-led"],
            falsifiers=["planner-only swap reproduces onset?"],
        )
        raw = json.loads(ex.model_dump_json())
        ex2 = Explanation.model_validate(raw)
        assert ex2.confidence == 0.78
        assert ex2.tier == "tier_2"

    def test_tier_validation(self):
        with pytest.raises(ValidationError):
            Explanation(id="x", event_id="e", label="bad", tier="tier_99")


# ── Case ─────────────────────────────────────────────────────────────────

class TestCase:
    def test_roundtrip(self):
        run_a = Run(id="a", world_model_ref="/w1.pth", planner_config={}, env_config={})
        run_b = Run(id="b", world_model_ref="/w2.pth", planner_config={}, env_config={})
        c = Case(
            id="case-001",
            project_id="proj-f1",
            run_a=run_a,
            run_b=run_b,
        )
        raw = json.loads(c.model_dump_json())
        c2 = Case.model_validate(raw)
        assert c2.id == "case-001"
        assert c2.run_a.world_model_ref == "/w1.pth"
        assert c2.run_b is not None
        assert c2.run_b.world_model_ref == "/w2.pth"

    def test_run_b_defaults_none(self):
        run = Run(id="x", planner_config={}, env_config={})
        c = Case(id="solo", run_a=run)
        assert c.run_b is None
