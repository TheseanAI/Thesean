"""Test raster_size inference from fake state_dict shapes.

No real checkpoints or model code needed — we only test the math that
maps encoder weight shapes → raster_size and aux_dim.
"""

import torch
import pytest

from psystack.adapters.f1.world_model import F1WorldModelAdapter


def _make_fake_state_dict(raster_size: int, aux_dim: int) -> dict[str, torch.Tensor]:
    """Build a minimal state_dict with the two keys the inference reads.

    Encoder architecture:
      4 stride-2 convs → spatial dim = raster_size / 16
      CNN output flat = 256 * (raster_size/16)^2
      aux embedding = 32 (fixed)
      fc input = cnn_flat + 32

    So encoder.fc.0.weight has shape (out_features, cnn_flat + 32)
    and encoder.aux_mlp.0.weight has shape (32, aux_dim)
    """
    spatial = raster_size // 16
    cnn_flat = 256 * spatial * spatial
    fc_in = cnn_flat + 32  # 32 = aux embedding size

    return {
        "encoder.fc.0.weight": torch.zeros(128, fc_in),  # out_features doesn't matter
        "encoder.aux_mlp.0.weight": torch.zeros(32, aux_dim),
    }


def _infer(state_dict: dict[str, torch.Tensor]) -> tuple[int, int]:
    """Run the same math as F1WorldModelAdapter.load() without loading a real model."""
    fc_in = state_dict["encoder.fc.0.weight"].shape[1]
    aux_emb = 32
    cnn_flat = fc_in - aux_emb
    raster_size = int(16 * (cnn_flat / 256) ** 0.5)
    aux_dim = state_dict["encoder.aux_mlp.0.weight"].shape[1]
    return raster_size, aux_dim


# ── Parametrized: cover the sizes we expect to encounter ─────────────

@pytest.mark.parametrize("raster_size, aux_dim", [
    (32, 8),
    (48, 12),
    (64, 16),   # current default
    (96, 16),
    (128, 24),
    (128, 16),
    (256, 32),
])
def test_infer_raster_size(raster_size: int, aux_dim: int):
    sd = _make_fake_state_dict(raster_size, aux_dim)
    got_raster, got_aux = _infer(sd)
    assert got_raster == raster_size, f"expected raster_size={raster_size}, got {got_raster}"
    assert got_aux == aux_dim, f"expected aux_dim={aux_dim}, got {got_aux}"


# ── Verify defaults before load() ────────────────────────────────────

def test_defaults_before_load():
    adapter = F1WorldModelAdapter()
    assert adapter.raster_size == 64
    assert adapter.aux_dim == 16


# ── Verify factory wiring ────────────────────────────────────────────

def test_default_env_config_uses_world_model_raster_size():
    """default_env_config should use world_model.raster_size when provided."""
    from psystack.adapters.f1.factory import F1AdapterFactory

    factory = F1AdapterFactory()

    # Without world model — default 64
    cfg_default = factory.default_env_config("FakeTrack")
    assert cfg_default["raster_size"] == 64

    # With a mock world model that reports raster_size=128
    class FakeWM:
        @property
        def raster_size(self) -> int:
            return 128
        @property
        def aux_dim(self) -> int:
            return 24

    cfg_128 = factory.default_env_config("FakeTrack", world_model=FakeWM())  # type: ignore[arg-type]
    assert cfg_128["raster_size"] == 128
