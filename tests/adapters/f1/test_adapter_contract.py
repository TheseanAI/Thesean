"""Adapter contract tests — verify any AdapterFactory satisfies the Protocol."""

from __future__ import annotations

from pathlib import Path

from thesean.core.contracts import (
    AdapterFactory,
    EnvPlugin,
    MetricPlugin,
    PlannerPlugin,
    WorldModelPlugin,
)
from thesean.pipeline.episodes import run_episodes


class TestAdapterContract:
    """Run against DummyAdapterFactory by default (via dummy_factory fixture).

    The F1 adapter can be tested by overriding the factory fixture
    in an F1-specific conftest when THESEAN_F1_REPO is set.
    """

    def test_is_adapter_factory(self, dummy_factory: AdapterFactory) -> None:
        assert isinstance(dummy_factory, AdapterFactory)

    def test_bind_repo(self, dummy_factory: AdapterFactory, tmp_path: Path) -> None:
        dummy_factory.bind_repo(tmp_path)

    def test_create_env_returns_env_plugin(self, dummy_factory: AdapterFactory) -> None:
        env = dummy_factory.create_env({"max_steps": 3})
        assert isinstance(env, EnvPlugin)

    def test_create_world_model_returns_plugin(self, dummy_factory: AdapterFactory) -> None:
        wm = dummy_factory.create_world_model("dummy.pth")
        assert isinstance(wm, WorldModelPlugin)

    def test_create_planner_returns_plugin(self, dummy_factory: AdapterFactory) -> None:
        wm = dummy_factory.create_world_model("dummy.pth")
        p = dummy_factory.create_planner({"horizon": 5}, wm)
        assert isinstance(p, PlannerPlugin)

    def test_get_metrics_returns_metric_plugins(self, dummy_factory: AdapterFactory) -> None:
        metrics = dummy_factory.get_metrics()
        assert len(metrics) > 0
        for m in metrics:
            assert isinstance(m, MetricPlugin)
            assert isinstance(m.metric_id(), str)
            assert isinstance(m.higher_is_better(), bool)

    def test_discover_weights_shape(self, dummy_factory: AdapterFactory, tmp_path: Path) -> None:
        weights = dummy_factory.discover_weights(tmp_path)
        assert isinstance(weights, list)
        for w in weights:
            assert "name" in w
            assert "path" in w

    def test_discover_envs_returns_strings(
        self, dummy_factory: AdapterFactory, tmp_path: Path
    ) -> None:
        envs = dummy_factory.discover_envs(tmp_path)
        assert isinstance(envs, list)
        assert all(isinstance(e, str) for e in envs)

    def test_default_configs_are_dicts(self, dummy_factory: AdapterFactory) -> None:
        assert isinstance(dummy_factory.default_planner_config(), dict)
        envs = dummy_factory.discover_envs(Path("."))
        if envs:
            assert isinstance(dummy_factory.default_env_config(envs[0]), dict)

    def test_episode_runner_completes(self, dummy_factory: AdapterFactory) -> None:
        env = dummy_factory.create_env({"max_steps": 3})
        wm = dummy_factory.create_world_model("dummy.pth")
        planner = dummy_factory.create_planner({"horizon": 5}, wm)

        episodes = run_episodes(env, planner, num_episodes=1, seed=42)
        assert len(episodes) == 1

        ep = episodes[0]
        assert "episode_id" in ep
        assert "steps" in ep
        assert "total_steps" in ep
        assert "total_reward" in ep
        assert "final_track_progress" in ep
        assert ep["total_steps"] > 0

    def test_metrics_compute_on_episodes(self, dummy_factory: AdapterFactory) -> None:
        env = dummy_factory.create_env({"max_steps": 3})
        wm = dummy_factory.create_world_model("dummy.pth")
        planner = dummy_factory.create_planner({"horizon": 5}, wm)
        episodes = run_episodes(env, planner, num_episodes=2, seed=42)

        for metric in dummy_factory.get_metrics():
            result = metric.compute(episodes)
            assert "primary_value" in result
            assert isinstance(result["primary_value"], int | float)
