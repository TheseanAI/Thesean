"""Tests for Phase 4B: LiveStepUpdate, step_callback, and queue helpers."""

from __future__ import annotations

import pickle
import queue

import pytest

from thesean.pipeline.live_update import LiveStepUpdate


class TestLiveStepUpdatePicklable:
    def test_roundtrip(self):
        update = LiveStepUpdate(
            run_id="a",
            episode_idx=0,
            episode_total=5,
            step=42,
            progress=0.47,
            state={"velocity": 12.3, "lidar": [0.1, 0.2]},
            action=[0.12, 0.80, 0.00],
            reward=1.23,
            done=False,
            info={"on_track": True},
        )
        data = pickle.dumps(update)
        restored = pickle.loads(data)
        assert restored == update
        assert restored.run_id == "a"
        assert restored.side == "a"  # backward-compat alias
        assert restored.step == 42
        assert restored.state["velocity"] == 12.3
        assert restored.car_state["velocity"] == 12.3  # backward-compat alias

    def test_frozen(self):
        update = LiveStepUpdate(run_id="a", episode_idx=0, episode_total=1, step=0, progress=0.0)
        with pytest.raises(AttributeError):
            update.step = 99  # type: ignore[misc]


class TestQueuePutNewest:
    def test_drops_oldest_when_full(self):
        from thesean.tui.app import _queue_put_newest

        q: queue.Queue = queue.Queue(maxsize=2)
        _queue_put_newest(q, "a")
        _queue_put_newest(q, "b")
        # Queue is now full
        _queue_put_newest(q, "c")
        # Should have dropped "a", queue should contain "b" and "c"
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert items == ["b", "c"]

    def test_put_into_empty_queue(self):
        from thesean.tui.app import _queue_put_newest

        q: queue.Queue = queue.Queue(maxsize=5)
        _queue_put_newest(q, "x")
        assert q.get_nowait() == "x"


class TestStepCallbackInRunEpisodes:
    """Test that step_callback receives correct shape from run_episodes."""

    def test_callback_receives_correct_keys(self):
        """Mock env/planner and verify callback dict shape."""
        from unittest.mock import MagicMock

        import numpy as np

        from thesean.pipeline.episodes import run_episodes

        # Mock env
        env = MagicMock()
        env.reset.return_value = {"aux": np.array([1.0, 2.0])}
        env.get_car_state.return_value = {"velocity": 10.0}
        env.get_progress.return_value = 0.5

        # env.step returns (obs, reward, done, info)
        env.step.return_value = (
            {"aux": np.array([1.0, 2.0])},
            1.0,
            True,
            {"on_track": True, "termination": "max_steps"},
        )

        # Mock planner
        planner = MagicMock()
        planner.act.return_value = np.array([0.1, 0.8, 0.0])

        received = []
        def cb(raw: dict) -> None:
            received.append(raw)

        run_episodes(env, planner, num_episodes=1, seed=42, step_callback=cb)

        assert len(received) == 1
        raw = received[0]
        expected_keys = {"step_idx", "car_state", "action", "reward", "done", "info", "track_progress"}
        assert set(raw.keys()) == expected_keys
        assert raw["step_idx"] == 0
        assert raw["reward"] == 1.0
        assert raw["done"] is True
        assert isinstance(raw["action"], list)

    def test_callback_none_no_error(self):
        """run_episodes with step_callback=None still works."""
        from unittest.mock import MagicMock

        import numpy as np

        from thesean.pipeline.episodes import run_episodes

        env = MagicMock()
        env.reset.return_value = {"aux": np.array([1.0])}
        env.get_car_state.return_value = {"velocity": 5.0}
        env.get_progress.return_value = 0.0
        env.step.return_value = (
            {"aux": np.array([1.0])},
            0.5,
            True,
            {"termination": "done"},
        )

        planner = MagicMock()
        planner.act.return_value = np.array([0.0, 0.0, 0.0])

        episodes = run_episodes(env, planner, num_episodes=1, seed=0, step_callback=None)
        assert len(episodes) == 1
        assert len(episodes[0]["steps"]) == 1
