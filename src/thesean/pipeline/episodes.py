"""Episode runner: steps env + planner, collects per-step data with deterministic seeding."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import torch

from thesean.core.contracts import EnvPlugin, PlannerPlugin


def run_episodes(
    env: EnvPlugin,
    planner: PlannerPlugin,
    num_episodes: int,
    seed: int = 42,
    step_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Run N episodes with deterministic seeding per episode."""
    episodes = []

    for ep_idx in range(num_episodes):
        ep_seed = seed + ep_idx

        # Mandatory seeding before each episode.
        # Note: Paired episodes are not truly paired due to CEM RNG consumption
        # divergence. The seed provides a consistent starting point but trajectories
        # diverge within episodes as different models cause different planner random
        # draws. Bootstrap p-values are approximate.
        np.random.seed(ep_seed)
        torch.manual_seed(ep_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(ep_seed)

        planner.reset()
        obs = env.reset(seed=ep_seed)

        steps = []
        total_reward = 0.0
        done = False
        termination = "max_steps"

        step_idx = 0
        while not done:
            car_state = env.get_car_state()
            track_progress = env.get_progress()  # Fix #2: explicit get_progress()

            action = planner.act(obs, car_state=car_state)

            obs_next, reward, done, info = env.step(action)

            steps.append({
                "obs": {"aux": obs["aux"].tolist() if hasattr(obs["aux"], "tolist") else obs["aux"]},
                "action": action.tolist() if hasattr(action, "tolist") else list(action),
                "reward": float(reward),
                "done": done,
                "info": _serialize_info(info),
                "car_state": car_state,
                "track_progress": float(track_progress),
            })

            if step_callback is not None:
                step_callback({
                    "step_idx": step_idx,
                    "car_state": car_state,
                    "action": action.tolist() if hasattr(action, "tolist") else list(action),
                    "reward": float(reward),
                    "done": done,
                    "info": info,
                    "track_progress": float(track_progress),
                })

            total_reward += reward
            obs = obs_next
            step_idx += 1

            if done and "termination" in info:
                termination = info["termination"]

        # Use last pre-step progress — env.get_progress() may return 0 after done
        final_progress = track_progress

        episodes.append({
            "episode_id": f"ep_{ep_idx:04d}",
            "steps": steps,
            "total_steps": len(steps),
            "final_track_progress": float(final_progress),
            "total_reward": float(total_reward),
            "termination": termination,
            "fastest_lap_time": info.get("fastest_lap_time"),
            "lap_count": info.get("lap_count", 0),
        })

    return episodes


def _serialize_info(info: dict) -> dict:
    """Make info JSON-serializable."""
    out = {}
    for k, v in info.items():
        if isinstance(v, bool | int | float | str | type(None)):
            out[k] = v
        elif isinstance(v, np.ndarray):
            out[k] = v.tolist()
        else:
            out[k] = str(v)
    return out
