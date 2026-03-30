"""F1-specific adapter factory — the single place that knows about F1."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thesean.adapters.f1.env import F1EnvAdapter
from thesean.adapters.f1.planner import F1PlannerAdapter
from thesean.adapters.f1.signals import F1SignalTranslator
from thesean.adapters.f1.world_model import F1WorldModelAdapter
from thesean.core.contracts import (
    EnvPlugin,
    MetricPlugin,
    PanelProvider,
    PlannerPlugin,
    SignalTranslator,
    WorldModelPlugin,
)
from thesean.evaluation.metrics import ALL_METRICS


class F1AdapterFactory:
    """Implements AdapterFactory using F1 adapters."""

    def __init__(self) -> None:
        self._repo: Path | None = None

    def bind_repo(self, repo: Path) -> None:
        """Prepare the F1 repo for use: validate and add to sys.path."""
        repo = repo.expanduser().resolve()
        if not repo.is_dir():
            raise ValueError(f"Adapter repo path does not exist: {repo}")
        self._repo = repo
        repo_str = str(repo)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

    def create_env(self, config: dict[str, Any]) -> EnvPlugin:
        env = F1EnvAdapter()
        env.configure(config)
        return env

    def create_world_model(self, weights_path: str, device: str = "cpu") -> WorldModelPlugin:
        wm = F1WorldModelAdapter()
        wm.load(weights_path, device=device)
        return wm

    def create_planner(self, config: dict[str, Any], world_model: WorldModelPlugin) -> PlannerPlugin:
        planner = F1PlannerAdapter()
        planner.configure(config, world_model)
        return planner

    def get_metrics(self) -> list[MetricPlugin]:
        return list(ALL_METRICS)

    def discover_weights(self, repo: Path) -> list[dict[str, Any]]:
        """Scan checkpoints/*.pth, return [{name, path, size_mb, mtime}, ...] newest-first."""
        ckpt_dir = repo / "checkpoints"
        if not ckpt_dir.is_dir():
            return []
        results = []
        for p in ckpt_dir.glob("*.pth"):
            st = p.stat()
            results.append({
                "name": p.name,
                "path": str(p.resolve()),
                "size_mb": round(st.st_size / 1_048_576, 1),
                "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                         .strftime("%Y-%m-%d %H:%M"),
            })
        return sorted(results, key=lambda w: w["mtime"], reverse=True)

    def discover_envs(self, repo: Path) -> list[str]:
        """Scan tracks/*.csv, return sorted track names (stems)."""
        tracks_dir = repo / "tracks"
        if not tracks_dir.is_dir():
            return []
        return sorted(p.stem for p in tracks_dir.glob("*.csv"))

    def discover_controllers(self) -> list[dict[str, Any]]:
        """Discover all scripted controller classes from data.controllers.

        Returns list of dicts: [{"name": "ScriptedPolicy", "requires_track": True}, ...]
        Requires bind_repo() to have been called first (sys.path must include F1 repo).
        """
        import importlib
        import inspect as _inspect

        mod = importlib.import_module("data.controllers")
        controllers: list[dict[str, Any]] = []
        for name, cls in _inspect.getmembers(mod, _inspect.isclass):
            if name.endswith("Policy"):
                sig = _inspect.signature(cls.__init__)
                requires_track = "track" in sig.parameters
                controllers.append({
                    "name": name,
                    "requires_track": requires_track,
                })
        return sorted(controllers, key=lambda c: c["name"])

    def create_scripted_controller(self, controller_name: str, track: Any = None) -> Any:
        """Create a ScriptedControllerAdapter for the named controller.

        Args:
            controller_name: Class name from data.controllers (e.g. "ScriptedPolicy")
            track: Track object (required for track-dependent controllers)
        """
        import importlib

        mod = importlib.import_module("data.controllers")
        cls = getattr(mod, controller_name)
        from thesean.adapters.f1.controllers import ScriptedControllerAdapter
        return ScriptedControllerAdapter(cls, track=track)

    def default_planner_config(self) -> dict[str, Any]:
        return {"num_candidates": 400, "horizon": 25, "iterations": 4, "num_elites": 40}

    def default_env_config(self, env_id: str, world_model: WorldModelPlugin | None = None) -> dict[str, Any]:
        """Build full env config for given track name. Paths are absolute if repo is bound.

        If world_model is provided, raster_size is inferred from checkpoint weights.
        """
        raster_size = world_model.raster_size if world_model is not None else 64
        track_csv = f"tracks/{env_id}.csv"
        if self._repo is not None:
            track_csv = str(self._repo / track_csv)
        return {
            "track_csv": track_csv,
            "max_speed": 50.0, "dt": 0.1, "max_steps": 1000,
            "max_steer_rate": 3.5, "off_track_tolerance": 10,
            "raster_size": raster_size, "pixels_per_meter": 3.0,
            "progress_reward": 0.02, "off_track_penalty": 0.5,
            "step_penalty": 0.005, "lap_bonus": 1.0,
        }

    # ── Phase 3 optional methods ──────────────────────────────────────────

    def detect_project(self, repo: Path) -> dict[str, Any]:
        """Scan F1 repo for available assets."""
        repo = repo.expanduser().resolve()
        assets: dict[str, Any] = {
            "weights": self.discover_weights(repo),
            "envs": self.discover_envs(repo),
            "scenarios": [],
            "configs": [],
        }
        # Scan for config files
        config_dir = repo / "configs"
        if config_dir.is_dir():
            assets["configs"] = sorted(p.name for p in config_dir.glob("*.py"))
        return assets

    def get_signal_translator(self) -> SignalTranslator | None:
        return F1SignalTranslator()

    def get_panel_providers(self) -> list[PanelProvider]:
        return [F1TrackPanel()]


class F1TrackPanel:
    """PanelProvider for F1 track visualization."""

    def panel_id(self) -> str:
        return "f1_track"

    def panel_label(self) -> str:
        return "F1 Track View"

    def load_track_geometry(self, track_csv: str) -> list[tuple[float, float]]:
        """Load (x, y) centerline points from a track CSV file."""
        import csv

        points: list[tuple[float, float]] = []
        with open(track_csv) as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].strip().startswith("#"):
                    continue
                try:
                    points.append((float(row[0].strip()), float(row[1].strip())))
                except (ValueError, IndexError):
                    continue
        return points
