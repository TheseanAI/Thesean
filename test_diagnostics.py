#!/usr/bin/env python3
"""Pipeline diagnostic script — isolates where array shape errors occur."""

import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
F1_REPO = Path("~/f1worldmodel-main").expanduser()
WEIGHTS = str(F1_REPO / "checkpoints" / "world_model_v1.pth")
MAX_STEPS = 10


def _setup():
    """Add F1 repo to sys.path and return a configured factory."""
    from thesean.adapters.f1.factory import F1AdapterFactory

    factory = F1AdapterFactory()
    factory.bind_repo(F1_REPO)
    return factory


def _fmt_shape(arr):
    """Format array shape + dtype."""
    dtype = getattr(arr, "dtype", type(arr).__name__)
    shape = getattr(arr, "shape", "?")
    return f"shape={shape} {dtype}"


# ── Phase 1: Layer-by-layer diagnostics ─────────────────────────────────────

def phase1():
    print("\n=== PHASE 1: Pipeline Layer Diagnostics ===\n")

    factory = _setup()

    # Step 1: env.reset()
    obs = None
    try:
        env_config = {**factory.default_env_config("Monza"), "max_steps": MAX_STEPS}
        env = factory.create_env(env_config)
        obs = env.reset(seed=42)
        raster_info = _fmt_shape(obs["raster"])
        aux_info = _fmt_shape(obs["aux"])
        print(f"[PASS] env.reset()         — raster: {raster_info}, aux: {aux_info}")
    except Exception:
        print(f"[FAIL] env.reset()\n{traceback.format_exc()}")
        return False

    # Step 2: world model load
    wm = None
    try:
        wm = factory.create_world_model(WEIGHTS)
        print(f"[PASS] world_model.load()  — {Path(WEIGHTS).name}")
    except Exception:
        print(f"[FAIL] world_model.load()\n{traceback.format_exc()}")
        return False

    # Step 3: adapter encode (uses F1WorldModelAdapter.encode)
    import torch

    try:
        latent = wm.encode(obs)
        print(f"[PASS] adapter.encode(obs) — latent {_fmt_shape(latent)}")
    except Exception:
        print(f"[FAIL] adapter.encode(obs)\n{traceback.format_exc()}")
        return False

    # Step 4: raw model encode (what CEMPlanner actually calls)
    try:
        raster_t = torch.from_numpy(obs["raster"]).float().unsqueeze(0)
        aux_t = torch.from_numpy(obs["aux"]).float().unsqueeze(0)
        print(f"       raw tensors — raster: {raster_t.shape}, aux: {aux_t.shape}")
        raw_model = wm.get_raw_model()
        with torch.no_grad():
            z = raw_model.encode(raster_t, aux_t)
        print(f"[PASS] raw model.encode()  — latent {_fmt_shape(z)}")
    except Exception:
        print(f"[FAIL] raw model.encode()\n{traceback.format_exc()}")
        return False

    # Step 5: planner init
    planner = None
    planner_cfg = factory.default_planner_config()
    try:
        planner = factory.create_planner(planner_cfg, wm)
        print(
            f"[PASS] planner.configure() — CEMPlanner("
            f"h={planner_cfg['horizon']}, n={planner_cfg['num_candidates']}, "
            f"k={planner_cfg['num_elites']}, iter={planner_cfg['iterations']})"
        )
    except Exception:
        print(f"[FAIL] planner.configure()\n{traceback.format_exc()}")
        return False

    # Step 6: single planner.act() call
    try:
        planner.reset()
        car_state = env.get_car_state()
        action = planner.act(obs, car_state=car_state)
        print(f"[PASS] planner.act(obs)    — action {_fmt_shape(action)}")
    except Exception:
        print(f"[FAIL] planner.act(obs)\n{traceback.format_exc()}")
        return False

    # Step 7: full episode loop
    try:
        from thesean.pipeline.episodes import run_episodes

        env2 = factory.create_env({**factory.default_env_config("Monza"), "max_steps": MAX_STEPS})
        planner2 = factory.create_planner(factory.default_planner_config(), wm)
        episodes = run_episodes(env2, planner2, 1, seed=42)
        ep = episodes[0]
        print(
            f"[PASS] run_episodes()      — "
            f"{ep['total_steps']} steps, progress={ep['final_track_progress']:.3f}, "
            f"term={ep['termination']}"
        )
    except Exception:
        print(f"[FAIL] run_episodes()\n{traceback.format_exc()}")
        return False

    return True


# ── Phase 2: Combo matrix ──────────────────────────────────────────────────

def _run_combo(track, planner_overrides, label):
    """Worker function for subprocess — runs one combo, returns result dict."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    try:
        factory = _setup()

        env_config = {**factory.default_env_config(track), "max_steps": MAX_STEPS}
        env = factory.create_env(env_config)

        wm = factory.create_world_model(WEIGHTS)

        planner_cfg = {**factory.default_planner_config(), **planner_overrides}
        planner = factory.create_planner(planner_cfg, wm)

        from thesean.pipeline.episodes import run_episodes

        episodes = run_episodes(env, planner, 1, seed=42)
        ep = episodes[0]
        return {
            "label": label,
            "status": "PASS",
            "detail": f"{ep['total_steps']} steps, progress={ep['final_track_progress']:.3f}",
        }
    except Exception:
        return {
            "label": label,
            "status": "FAIL",
            "detail": traceback.format_exc().strip().split("\n")[-1],
        }


def phase2(factory):
    print("\n=== PHASE 2: Combo Matrix ===\n")

    tracks = factory.discover_envs(F1_REPO)
    planner_variants = [
        ({}, "default"),
        ({"horizon": 8}, "horizon=8"),
        ({"horizon": 50}, "horizon=50"),
        ({"num_candidates": 100}, "candidates=100"),
        ({"num_candidates": 800}, "candidates=800"),
        ({"num_elites": 10}, "elites=10"),
        ({"iterations": 2}, "iterations=2"),
    ]

    combos = []
    # All tracks × default planner
    for track in tracks:
        combos.append((track, {}, f"{track:20s} | default"))
    # Monza × planner variants (skip default, already covered)
    for overrides, desc in planner_variants[1:]:
        combos.append(("Monza", overrides, f"{'Monza':20s} | {desc}"))

    print(f"Running {len(combos)} combos across {os.cpu_count()} workers...\n")
    print(f"{'Track/Config':<45s} | Status | Detail")
    print("-" * 90)

    results = []
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        futures = {
            pool.submit(_run_combo, track, overrides, label): label
            for track, overrides, label in combos
        }
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            tag = "PASS" if r["status"] == "PASS" else "FAIL"
            print(f"{r['label']:<45s} | {tag:4s}   | {r['detail']}")

    # Summary
    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\n{'='*90}")
    print(f"Total: {passes} passed, {fails} failed out of {len(results)}")

    if fails:
        print("\nFailed combos:")
        for r in sorted(results, key=lambda x: x["label"]):
            if r["status"] == "FAIL":
                print(f"  {r['label']} — {r['detail']}")


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    phase1_ok = phase1()

    if phase1_ok:
        factory = _setup()
        phase2(factory)
    else:
        print("\n^^^ Phase 1 failed — fix the above before running combo tests.")

    print()
