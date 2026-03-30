"""Paired episode runner — lockstep A/B execution with pair-aware telemetry."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import numpy as np
import torch

from thesean.core.contracts import EnvPlugin, PlannerPlugin
from thesean.pipeline.episodes import _serialize_info
from thesean.pipeline.live_update import LivePairFrame, LiveStepUpdate


class EvalCancelled(Exception):
    """Raised when the user cancels a running evaluation."""


def run_paired_episodes(
    env_a: EnvPlugin,
    env_b: EnvPlugin,
    planner_a: PlannerPlugin,
    planner_b: PlannerPlugin,
    num_episodes: int,
    seed: int = 42,
    pair_callback: Callable[[LivePairFrame], None] | None = None,
    max_steps: int = 0,
    cancel_event: threading.Event | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run N episode pairs in lockstep.

    Both envs are stepped once per tick. One LivePairFrame emitted per tick.
    If one side finishes early, its update freezes.

    Returns (episodes_a, episodes_b) in the same format as run_episodes().
    """
    all_episodes_a: list[dict[str, Any]] = []
    all_episodes_b: list[dict[str, Any]] = []

    for ep_idx in range(num_episodes):
        ep_seed = seed + ep_idx

        # Deterministic seeding
        np.random.seed(ep_seed)
        torch.manual_seed(ep_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(ep_seed)

        planner_a.reset()
        planner_b.reset()
        obs_a = env_a.reset(seed=ep_seed)
        obs_b = env_b.reset(seed=ep_seed)

        steps_a: list[dict[str, Any]] = []
        steps_b: list[dict[str, Any]] = []
        total_reward_a = 0.0
        total_reward_b = 0.0
        done_a = False
        done_b = False
        termination_a = "max_steps"
        termination_b = "max_steps"
        info_a: dict[str, Any] = {}
        info_b: dict[str, Any] = {}

        # Frozen terminal state for the side that finishes first
        last_update_a: LiveStepUpdate | None = None
        last_update_b: LiveStepUpdate | None = None
        # Track last known progress — env may reset to 0 after done=True
        last_progress_a = 0.0
        last_progress_b = 0.0

        tick = 0
        while not (done_a and done_b):
            if cancel_event is not None and cancel_event.is_set():
                raise EvalCancelled("Evaluation cancelled by user")
            # Step A
            if not done_a:
                car_state_a = env_a.get_car_state()
                progress_a = env_a.get_progress()
                action_a = planner_a.act(obs_a, car_state=car_state_a)
                obs_next_a, reward_a, done_a, info_a = env_a.step(action_a)
                last_progress_a = float(progress_a)

                action_list_a = action_a.tolist() if hasattr(action_a, "tolist") else list(action_a)
                steps_a.append({
                    "obs": {"aux": obs_a["aux"].tolist() if hasattr(obs_a["aux"], "tolist") else obs_a["aux"]},
                    "action": action_list_a,
                    "reward": float(reward_a),
                    "done": done_a,
                    "info": _serialize_info(info_a),
                    "car_state": car_state_a,
                    "track_progress": float(progress_a),
                })
                total_reward_a += reward_a
                obs_a = obs_next_a

                if done_a and "termination" in info_a:
                    termination_a = info_a["termination"]

                last_update_a = LiveStepUpdate(
                    run_id="a", episode_idx=ep_idx, episode_total=num_episodes,
                    step=tick, progress=float(progress_a), reward=float(reward_a),
                    done=done_a,
                    termination=info_a.get("termination") if done_a else None,
                    state=car_state_a, action=action_list_a, info=_serialize_info(info_a),  # type: ignore[arg-type]
                )

            if cancel_event is not None and cancel_event.is_set():
                raise EvalCancelled("Evaluation cancelled by user")
            # Step B
            if not done_b:
                car_state_b = env_b.get_car_state()
                progress_b = env_b.get_progress()
                action_b = planner_b.act(obs_b, car_state=car_state_b)
                obs_next_b, reward_b, done_b, info_b = env_b.step(action_b)
                last_progress_b = float(progress_b)

                action_list_b = action_b.tolist() if hasattr(action_b, "tolist") else list(action_b)
                steps_b.append({
                    "obs": {"aux": obs_b["aux"].tolist() if hasattr(obs_b["aux"], "tolist") else obs_b["aux"]},
                    "action": action_list_b,
                    "reward": float(reward_b),
                    "done": done_b,
                    "info": _serialize_info(info_b),
                    "car_state": car_state_b,
                    "track_progress": float(progress_b),
                })
                total_reward_b += reward_b
                obs_b = obs_next_b

                if done_b and "termination" in info_b:
                    termination_b = info_b["termination"]

                last_update_b = LiveStepUpdate(
                    run_id="b", episode_idx=ep_idx, episode_total=num_episodes,
                    step=tick, progress=float(progress_b), reward=float(reward_b),
                    done=done_b,
                    termination=info_b.get("termination") if done_b else None,
                    state=car_state_b, action=action_list_b, info=_serialize_info(info_b),  # type: ignore[arg-type]
                )

            # Emit pair frame
            if pair_callback is not None:
                frame = LivePairFrame(
                    episode_idx=ep_idx,
                    episode_total=num_episodes,
                    tick=tick,
                    a=last_update_a,
                    b=last_update_b,
                    both_done=done_a and done_b,
                    max_steps=max_steps,
                )
                pair_callback(frame)

            tick += 1

        # Build episode records — use last tracked progress, not env.get_progress()
        # which may return 0 if the env auto-resets on done=True
        final_progress_a = last_progress_a
        final_progress_b = last_progress_b

        all_episodes_a.append({
            "episode_id": f"ep_{ep_idx:04d}",
            "steps": steps_a,
            "total_steps": len(steps_a),
            "final_track_progress": float(final_progress_a),
            "total_reward": float(total_reward_a),
            "termination": termination_a,
            "fastest_lap_time": info_a.get("fastest_lap_time"),
            "lap_count": info_a.get("lap_count", 0),
        })
        all_episodes_b.append({
            "episode_id": f"ep_{ep_idx:04d}",
            "steps": steps_b,
            "total_steps": len(steps_b),
            "final_track_progress": float(final_progress_b),
            "total_reward": float(total_reward_b),
            "termination": termination_b,
            "fastest_lap_time": info_b.get("fastest_lap_time"),
            "lap_count": info_b.get("lap_count", 0),
        })

    return all_episodes_a, all_episodes_b
