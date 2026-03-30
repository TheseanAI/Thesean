from __future__ import annotations

import torch


def degrade_model(
    src_path: str,
    dst_path: str,
    noise_scale: float = 0.3,
) -> None:
    """Load a world model checkpoint, add noise to predictor/head weights, save."""
    state_dict = torch.load(src_path, map_location="cpu", weights_only=True)

    degraded = {}
    for key, tensor in state_dict.items():
        if key.startswith("predictor.") or "_head." in key:
            noise = torch.randn_like(tensor) * noise_scale * tensor.abs().mean()
            degraded[key] = tensor + noise
        else:
            degraded[key] = tensor.clone()

    torch.save(degraded, dst_path)


def load_model(weights_path: str, device: str = "cpu"):
    """Convenience: load a WorldModel with weights."""
    from thesean.adapters.f1.world_model import F1WorldModelAdapter

    adapter = F1WorldModelAdapter()
    adapter.load(weights_path, device=device)
    return adapter
