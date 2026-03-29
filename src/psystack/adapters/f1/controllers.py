"""Scripted controller adapter — wraps F1 scripted policies as PlannerPlugin."""

from __future__ import annotations

import inspect
from typing import Any

import numpy as np


class ScriptedControllerAdapter:
    """Wraps a scripted controller to satisfy PlannerPlugin protocol.

    This enables the existing episode runner (run_episodes) to work with
    scripted controllers without a separate code path.
    """

    def __init__(self, controller_cls: type, track: Any | None = None) -> None:
        self._controller_cls = controller_cls
        self._track = track
        self._accepts_car_state = self._check_car_state(controller_cls)
        self._controller = self._make_controller()

    @staticmethod
    def _check_car_state(cls: type) -> bool:
        """Check if the controller's __call__ accepts a car_state kwarg."""
        sig = inspect.signature(cls.__call__)
        return "car_state" in sig.parameters

    def _make_controller(self) -> Any:
        """Instantiate the controller, passing track if the constructor accepts it."""
        sig = inspect.signature(self._controller_cls)
        if "track" in sig.parameters and self._track is not None:
            return self._controller_cls(self._track)
        return self._controller_cls()

    def planner_id(self) -> str:
        return f"scripted_{self._controller_cls.__name__}"

    def configure(self, config: dict[str, Any], world_model: Any = None) -> None:
        """No-op for scripted controllers."""
        pass

    def reset(self) -> None:
        """Re-instantiate the controller to reset all internal state.

        This is safer than manually resetting step_counter/panic_counter etc
        because it handles any future stateful controllers automatically.
        """
        self._controller = self._make_controller()

    def act(self, obs: dict[str, Any], car_state: dict[str, Any] | None = None) -> np.ndarray:
        """Delegate to the underlying controller's __call__."""
        if self._accepts_car_state:
            return self._controller(obs, car_state=car_state)  # type: ignore[no-any-return]
        return self._controller(obs)  # type: ignore[no-any-return]
