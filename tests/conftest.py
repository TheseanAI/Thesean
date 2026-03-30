"""Shared test fixtures: DummyAdapterFactory and workspace helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import tomli_w

from thesean.models import RunManifest
from thesean.models.case import Case
from thesean.models.run import Run

# ---------------------------------------------------------------------------
# Dummy adapter components — satisfy all Protocol contracts from protocols.py
# ---------------------------------------------------------------------------


class DummyEnv:
    def __init__(self) -> None:
        self._step: int = 0
        self._max_steps: int = 3

    def env_id(self) -> str:
        return "dummy"

    def configure(self, config: dict[str, Any]) -> None:
        self._max_steps = config.get("max_steps", 3)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        self._step = 0
        return {"aux": np.zeros(4)}

    def step(self, action: np.ndarray) -> tuple[dict, float, bool, dict]:
        self._step += 1
        done = self._step >= self._max_steps
        info: dict[str, Any] = {}
        if done:
            info["termination"] = "max_steps"
        return {"aux": np.zeros(4)}, 1.0, done, info

    def get_car_state(self) -> dict[str, Any]:
        return {"speed": 10.0, "position": [0.0, 0.0]}

    def get_progress(self) -> float:
        return min(self._step / max(self._max_steps, 1), 1.0)


class DummyWorldModel:
    def model_id(self) -> str:
        return "dummy"

    def load(self, weights_path: str, device: str = "cpu") -> None:
        pass

    def encode(self, obs: dict[str, Any]) -> Any:
        return np.zeros(4)

    def encode_target(self, obs: dict[str, Any]) -> Any:
        return np.zeros(4)

    def predict(self, latent: Any, action: np.ndarray) -> Any:
        return np.zeros(4)

    def predict_progress(self, latent: Any) -> float:
        return 0.5

    def predict_offtrack(self, latent: Any) -> float:
        return 0.0

    def get_raw_model(self) -> Any:
        return None


class DummyPlanner:
    def planner_id(self) -> str:
        return "dummy"

    def configure(self, config: dict[str, Any], world_model: Any) -> None:
        pass

    def reset(self) -> None:
        pass

    def act(self, obs: dict[str, Any], car_state: dict[str, Any] | None = None) -> np.ndarray:
        return np.zeros(2)


class DummyMetric:
    def metric_id(self) -> str:
        return "dummy_reward"

    def higher_is_better(self) -> bool:
        return True

    def compute(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        per_episode = [ep.get("total_reward", 0.0) for ep in episodes]
        mean_val = sum(per_episode) / len(per_episode) if per_episode else 0.0
        return {
            "primary_value": mean_val,
            "unit": "reward",
            "per_episode": per_episode,
            "breakdown": {},
        }


class DummyAdapterFactory:
    """Test adapter factory satisfying the AdapterFactory Protocol."""

    def bind_repo(self, repo: Path) -> None:
        pass

    def create_env(self, config: dict[str, Any]) -> DummyEnv:
        env = DummyEnv()
        env.configure(config)
        return env

    def create_world_model(self, weights_path: str, device: str = "cpu") -> DummyWorldModel:
        wm = DummyWorldModel()
        wm.load(weights_path, device)
        return wm

    def create_planner(self, config: dict[str, Any], world_model: Any) -> DummyPlanner:
        p = DummyPlanner()
        p.configure(config, world_model)
        return p

    def get_metrics(self) -> list[DummyMetric]:
        return [DummyMetric()]

    def discover_weights(self, repo: Path) -> list[dict[str, Any]]:
        return [
            {
                "name": "dummy.pth",
                "path": str(repo / "dummy.pth"),
                "size_mb": 1.0,
                "mtime": "2024-01-01",
            }
        ]

    def discover_envs(self, repo: Path) -> list[str]:
        return ["dummy_track"]

    def default_planner_config(self) -> dict[str, Any]:
        return {"horizon": 5}

    def default_env_config(self, env_id: str) -> dict[str, Any]:
        return {"max_steps": 3}

    def detect_project(self, repo: Path) -> dict[str, Any]:
        return {"weights": self.discover_weights(repo), "envs": self.discover_envs(repo)}

    def get_signal_translator(self) -> None:
        return None

    def get_panel_providers(self) -> list:
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dummy_factory() -> DummyAdapterFactory:
    return DummyAdapterFactory()


@pytest.fixture()
def dummy_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a workspace with dummy adapter config and manifests.

    Monkeypatches load_adapter_factory so RunContext uses DummyAdapterFactory.
    """
    ws = tmp_path / "ws"
    ws.mkdir()

    # thesean.toml
    with (ws / "thesean.toml").open("wb") as f:
        tomli_w.dump({"adapter": {"type": "dummy", "repo": str(tmp_path)}}, f)

    # Manifests — use identical configs so compare produces no regressions
    env_config: dict[str, Any] = {"max_steps": 3}
    planner_config: dict[str, Any] = {"horizon": 5}

    b = RunManifest(
        run_id="baseline",
        world_model_weights="dummy.pth",
        planner_config=planner_config,
        env_config=env_config,
        num_episodes=2,
        seed=42,
    )
    c = RunManifest(
        run_id="candidate",
        world_model_weights="dummy.pth",
        planner_config=planner_config,
        env_config=env_config,
        num_episodes=2,
        seed=42,
    )

    (ws / "baseline_manifest.json").write_text(b.model_dump_json(indent=2))
    (ws / "candidate_manifest.json").write_text(c.model_dump_json(indent=2))

    # case.json — RunContext loads this to derive manifests
    case = Case(
        id="test-case",
        track_ref="dummy_track",
        episode_count=2,
        run_a=Run(
            id="baseline",
            world_model_ref="dummy.pth",
            planner_config=planner_config,
            env_config=env_config,
            seed=42,
            num_episodes=2,
        ),
        run_b=Run(
            id="candidate",
            world_model_ref="dummy.pth",
            planner_config=planner_config,
            env_config=env_config,
            seed=42,
            num_episodes=2,
        ),
    )
    (ws / "case.json").write_text(case.model_dump_json(indent=2))

    # Monkeypatch adapter loading in RunContext
    monkeypatch.setattr(
        "thesean.pipeline.context.load_adapter_factory",
        lambda name: DummyAdapterFactory(),
    )

    return ws
