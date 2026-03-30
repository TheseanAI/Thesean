from __future__ import annotations

from typing import Any

import numpy as np
import torch


class WorldModelPredictionError:
    """MSE between predicted z_{t+1} and encode_target(obs_{t+1}).

    This metric re-runs episodes to capture rasters (not stored in episode data).
    It uses a scripted straight-ahead policy for determinism.
    """

    def metric_id(self) -> str:
        return "prediction_error"

    def higher_is_better(self) -> bool:
        return False

    def compute(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        # prediction_error requires world_model and env passed via episode metadata
        # If not available, return NaN
        if not episodes or "_world_model" not in episodes[0]:
            return {
                "primary_value": float("nan"),
                "unit": "mse",
                "per_episode": [],
                "breakdown": {"note": "world_model not available for prediction_error"},
            }

        world_model = episodes[0]["_world_model"]
        env = episodes[0]["_env"]
        seed = episodes[0].get("_seed", 42)
        num_episodes = len(episodes)
        max_eval_steps = 200  # limit steps for prediction error eval

        per_episode = []
        for ep_idx in range(num_episodes):
            np.random.seed(seed + ep_idx)
            torch.manual_seed(seed + ep_idx)

            obs = env.reset(seed=seed + ep_idx)
            errors = []

            # Scripted policy: gentle throttle, no steering
            action = np.array([0.0, 0.3, 0.0], dtype=np.float32)

            for _ in range(max_eval_steps):
                z_t = world_model.encode(obs)
                z_pred = world_model.predict(z_t, action)

                obs_next, _, done, _ = env.step(action)
                z_target = world_model.encode_target(obs_next)

                mse = torch.mean((z_pred - z_target) ** 2).item()
                errors.append(mse)

                obs = obs_next
                if done:
                    break

            per_episode.append(sum(errors) / len(errors) if errors else 0.0)

        return {
            "primary_value": sum(per_episode) / len(per_episode) if per_episode else 0.0,
            "unit": "mse",
            "per_episode": per_episode,
            "breakdown": {},
        }
