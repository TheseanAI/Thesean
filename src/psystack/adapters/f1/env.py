from __future__ import annotations

from typing import Any

import numpy as np


class F1EnvAdapter:
    """Wraps env.f1_env.F1Env to satisfy EnvPlugin protocol."""

    def __init__(self) -> None:
        self._env = None

    def env_id(self) -> str:
        return "f1_env"

    def configure(self, config: dict[str, Any]) -> None:
        import os
        import threading

        # Prevent pygame/SDL2 from initializing Cocoa display when imported
        # from a non-main thread (causes SIGABRT on macOS).
        if threading.current_thread() is not threading.main_thread():
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

        from configs.default import Config
        from env.f1_env import F1Env

        cfg = Config(**{k: v for k, v in config.items() if hasattr(Config, k)})
        self._env = F1Env.from_config(cfg)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        if self._env is None:
            raise RuntimeError("configure() must be called before reset()")
        # F1Env.reset() does not accept a seed parameter. Global RNG seeding
        # is handled by the runner. If F1Env adds seed support, forward it here.
        return self._env.reset()

    def step(self, action: np.ndarray) -> tuple[dict, float, bool, dict]:
        if self._env is None:
            raise RuntimeError("configure() must be called before step()")
        return self._env.step(action)

    def get_car_state(self) -> dict[str, Any]:
        return self._env.get_car_state()  # type: ignore[attr-defined, no-any-return]

    def get_progress(self) -> float:
        return self._env.get_progress()  # type: ignore[attr-defined, no-any-return]
