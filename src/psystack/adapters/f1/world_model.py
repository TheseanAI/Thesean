from __future__ import annotations

from typing import Any

import numpy as np
import torch


class F1WorldModelAdapter:
    """Wraps models.world_model.WorldModel to satisfy WorldModelPlugin protocol."""

    def __init__(self) -> None:
        self._model = None
        self._device = "cpu"

    def model_id(self) -> str:
        return "f1_world_model"

    def load(self, weights_path: str, device: str = "cpu") -> None:
        from models.world_model import WorldModel

        self._device = device
        model = WorldModel()
        state_dict = torch.load(weights_path, map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        self._model = model

    def encode(self, obs: dict[str, Any]) -> Any:
        if self._model is None:
            raise RuntimeError("load() must be called before encode()")
        raster = self._to_raster_tensor(obs)
        aux = self._to_aux_tensor(obs)
        with torch.no_grad():
            return self._model.encode(raster, aux)

    def encode_target(self, obs: dict[str, Any]) -> Any:
        if self._model is None:
            raise RuntimeError("load() must be called before encode_target()")
        raster = self._to_raster_tensor(obs)
        aux = self._to_aux_tensor(obs)
        with torch.no_grad():
            return self._model.get_target(raster, aux)

    def predict(self, latent: Any, action: np.ndarray) -> Any:
        if self._model is None:
            raise RuntimeError("load() must be called before predict()")
        action_t = torch.tensor(action, dtype=torch.float32, device=self._device)
        if action_t.dim() == 1:
            action_t = action_t.unsqueeze(0)
        with torch.no_grad():
            return self._model.predict(latent, action_t)

    def predict_progress(self, latent: Any) -> float:
        if self._model is None:
            raise RuntimeError("load() must be called before predict_progress()")
        with torch.no_grad():
            return self._model.progress_head(latent).item()  # type: ignore[no-any-return]

    def predict_offtrack(self, latent: Any) -> float:
        if self._model is None:
            raise RuntimeError("load() must be called before predict_offtrack()")
        with torch.no_grad():
            return torch.sigmoid(self._model.offtrack_head(latent)).item()  # type: ignore[no-any-return]

    def get_raw_model(self) -> Any:
        return self._model

    def _to_raster_tensor(self, obs: dict[str, Any]) -> torch.Tensor:
        raster = obs["raster"]
        if isinstance(raster, np.ndarray):
            raster = torch.tensor(raster, dtype=torch.float32, device=self._device)
        if raster.dim() == 3:
            raster = raster.unsqueeze(0)
        return raster  # type: ignore[no-any-return]

    def _to_aux_tensor(self, obs: dict[str, Any]) -> torch.Tensor:
        aux = obs["aux"]
        if isinstance(aux, np.ndarray):
            aux = torch.tensor(aux, dtype=torch.float32, device=self._device)
        if aux.dim() == 1:
            aux = aux.unsqueeze(0)
        return aux  # type: ignore[no-any-return]
