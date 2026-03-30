from __future__ import annotations

from typing import Any

import numpy as np

from thesean.core.contracts import WorldModelPlugin


class F1PlannerAdapter:
    """Wraps planner.mpc.CEMPlanner to satisfy PlannerPlugin protocol."""

    def __init__(self) -> None:
        self._planner = None

    def planner_id(self) -> str:
        return "f1_cem_planner"

    def configure(self, config: dict[str, Any], world_model: WorldModelPlugin) -> None:
        from planner.mpc import CEMPlanner

        config = dict(config)  # defensive copy — don't mutate caller's dict
        raw_model = world_model.get_raw_model()
        device = config.pop("device", "cpu") if "device" in config else "cpu"
        config.pop("seed", None)  # seed is a runner-level concern, not a CEM param
        try:
            self._planner = CEMPlanner(model=raw_model, device=device, **config)
        except TypeError as e:
            import inspect
            sig = inspect.signature(CEMPlanner.__init__)
            valid = set(sig.parameters.keys()) - {"self", "model", "device"}
            extra = set(config.keys()) - valid
            raise TypeError(
                f"CEMPlanner config error: {e}\n"
                f"  config keys passed: {sorted(config.keys())}\n"
                f"  valid CEM params:   {sorted(valid)}\n"
                f"  unexpected keys:    {sorted(extra) if extra else 'none'}"
            ) from e

    def reset(self) -> None:
        if self._planner is not None:
            import torch
            H = self._planner.horizon
            self._planner.mu = torch.zeros(H, 3, device=self._planner.device)
            self._planner.mu[:, 1] = 1.0  # match CEM default: 100% throttle warm-start
            # var is not reset — CEM recomputes var locally in __call__ each time

    def act(self, obs: dict[str, Any], car_state: dict[str, Any] | None = None) -> np.ndarray:
        if self._planner is None:
            raise RuntimeError("configure() must be called before act()")
        try:
            return self._planner(obs, car_state=car_state)
        except RuntimeError as e:
            shapes = {k: (v.shape if hasattr(v, "shape") else type(v).__name__) for k, v in obs.items()}
            raise RuntimeError(
                f"CEM planner failed: {e}\n"
                f"  obs shapes: {shapes}\n"
                f"  horizon={self._planner.horizon}, "
                f"candidates={self._planner.num_candidates}"
            ) from e
