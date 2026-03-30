#!/usr/bin/env python3
"""Generate example workspaces from real model classes.

Run: python3 examples/generate.py

Produces:
  examples/f1_demo_workspace/       — fully populated F1 workspace (ready state)
  examples/f1_demo_workspace_empty/ — draft F1 workspace (no results)
"""
from __future__ import annotations

import json
from pathlib import Path

from thesean.models.case import Case
from thesean.models.comparison import ComparisonReport, MetricComparison
from thesean.models.episode import EpisodeRecord, OutcomeSummary
from thesean.models.evaluation_result import ConfigSnapshot, EvaluationResult
from thesean.models.event import Event
from thesean.models.run import Run
from thesean.pipeline.state import RunState, StageState

ROOT = Path(__file__).parent


def _make_step(
    aux: list[float],
    action: list[float],
    velocity: float,
    theta: float,
    x: float,
    y: float,
    track_progress: float,
    reward: float,
    done: bool,
    info: dict | None = None,
) -> dict:
    return {
        "obs": {"aux": aux},
        "action": action,
        "car_state": {"velocity": velocity, "theta": theta, "x": x, "y": y},
        "track_progress": track_progress,
        "reward": reward,
        "done": done,
        "info": info or {},
    }


def _make_aux(n: int = 16) -> list[float]:
    return [0.1 * i for i in range(n)]


def generate_f1_workspace() -> None:
    ws = ROOT / "f1_demo_workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # -- thesean.toml --
    (ws / "thesean.toml").write_text(
        '[adapter]\ntype = "f1"\nrepo = "/path/to/f1tenth_gym"\n'
    )

    # -- case.json --
    run_a = Run(id="baseline", world_model_ref="dummy.pth", seed=42, horizon=5)
    run_b = Run(id="candidate", world_model_ref="dummy.pth", seed=42, horizon=5)
    case = Case(
        id="example-case",
        track_ref="dummy_track",
        episode_count=2,
        run_a=run_a,
        run_b=run_b,
    )
    (ws / "case.json").write_text(case.model_dump_json(indent=2))

    # -- workspace_state.json --
    (ws / "workspace_state.json").write_text(
        json.dumps({"case_state": "ready", "attempts": []}, indent=2)
    )

    # -- runs/a/episodes.json --
    (ws / "runs" / "a").mkdir(parents=True, exist_ok=True)
    episodes_a = [
        {
            "episode_id": "ep_0000",
            "steps": [
                _make_step(_make_aux(), [0.1, 0.8, 0.0], 10.0, 0.0, 0.0, 0.0, 0.0, 1.0, False),
                _make_step(_make_aux(), [0.2, 0.7, 0.0], 12.0, 0.1, 1.0, 0.1, 0.5, 1.5, False),
                _make_step(_make_aux(), [0.15, 0.75, 0.0], 11.0, 0.05, 2.0, 0.2, 0.95, 2.0, True),
            ],
            "total_steps": 3,
            "final_track_progress": 0.95,
            "total_reward": 4.5,
            "termination": None,
            "fastest_lap_time": None,
            "lap_count": 0,
        },
        {
            "episode_id": "ep_0001",
            "steps": [
                _make_step(_make_aux(), [0.3, 0.6, 0.0], 10.0, 0.0, 0.0, 0.0, 0.0, 1.0, False),
                _make_step(_make_aux(), [0.5, 0.4, 0.1], 8.0, 0.3, 0.5, 0.5, 0.3, 0.5, False),
                _make_step(_make_aux(), [0.6, 0.3, 0.2], 5.0, 0.5, 0.6, 0.8, 0.4, 0.0, True,
                           {"termination": "off_track", "offtrack_steps": 5}),
            ],
            "total_steps": 3,
            "final_track_progress": 0.4,
            "total_reward": 1.5,
            "termination": "off_track",
            "fastest_lap_time": None,
            "lap_count": 0,
        },
    ]
    (ws / "runs" / "a" / "episodes.json").write_text(json.dumps(episodes_a, indent=2))

    # -- runs/b/episodes.json --
    (ws / "runs" / "b").mkdir(parents=True, exist_ok=True)
    episodes_b = [
        {
            "episode_id": "ep_0000",
            "steps": [
                _make_step(_make_aux(), [0.1, 0.9, 0.0], 11.0, 0.0, 0.0, 0.0, 0.0, 1.2, False),
                _make_step(_make_aux(), [0.15, 0.85, 0.0], 13.0, 0.05, 1.2, 0.1, 0.6, 2.0, False),
                _make_step(_make_aux(), [0.12, 0.88, 0.0], 12.5, 0.02, 2.5, 0.15, 1.0, 2.5, True),
            ],
            "total_steps": 3,
            "final_track_progress": 1.0,
            "total_reward": 5.7,
            "termination": None,
            "fastest_lap_time": None,
            "lap_count": 0,
        },
        {
            "episode_id": "ep_0001",
            "steps": [
                _make_step(_make_aux(), [0.4, 0.5, 0.0], 9.0, 0.0, 0.0, 0.0, 0.0, 0.8, False),
                _make_step(_make_aux(), [0.6, 0.3, 0.15], 6.0, 0.4, 0.3, 0.6, 0.2, 0.3, False),
                _make_step(_make_aux(), [0.7, 0.2, 0.3], 4.0, 0.6, 0.4, 0.9, 0.3, 0.0, True,
                           {"termination": "off_track", "offtrack_steps": 7}),
            ],
            "total_steps": 3,
            "final_track_progress": 0.3,
            "total_reward": 1.1,
            "termination": "off_track",
            "fastest_lap_time": None,
            "lap_count": 0,
        },
    ]
    (ws / "runs" / "b" / "episodes.json").write_text(json.dumps(episodes_b, indent=2))

    # -- analysis/outcomes.json --
    (ws / "analysis").mkdir(parents=True, exist_ok=True)
    eps_a = [
        EpisodeRecord(episode_idx=0, final_track_progress=0.95, total_reward=4.5),
        EpisodeRecord(episode_idx=1, final_track_progress=0.4, total_reward=1.5, termination="off_track"),
    ]
    eps_b = [
        EpisodeRecord(episode_idx=0, final_track_progress=1.0, total_reward=5.7),
        EpisodeRecord(episode_idx=1, final_track_progress=0.3, total_reward=1.1, termination="off_track"),
    ]
    outcomes = OutcomeSummary(
        verdict="regression",
        primary_metric="final_track_progress",
        primary_metric_display="completion",
        baseline_value=0.675,
        candidate_value=0.65,
        delta_pct=-3.7,
        significant=True,
        regression_count=1,
        improvement_count=1,
        no_change_count=0,
        verdict_headline="Candidate underperformed baseline under the same planner setup.",
        primary_metric_line="completion: candidate 65% vs baseline 68% (-3.7%)",
        findings_count_line="1 metric regressed, 1 improved",
        top_run={"side": "a", "episode_id": "ep_0000"},
        recommended_run_ids=["ep_0000"],
        episodes_a=eps_a,
        episodes_b=eps_b,
    )
    (ws / "analysis" / "outcomes.json").write_text(outcomes.model_dump_json(indent=2))

    # -- analysis/events.json --
    evt_div = Event(
        id="evt-div-ep0-s1",
        type="divergence_window",
        step=1,
        severity="warning",
        score=0.35,
        persistence_k=2,
    )
    evt_off = Event(
        id="evt-off-ep1-s2",
        type="off_track_terminal",
        step=2,
        severity="critical",
        score=0.9,
        persistence_k=1,
    )
    events_data = {
        "events_by_episode": {
            "a": {
                "ep_0000": [evt_div.model_dump()],
                "ep_0001": [evt_off.model_dump()],
            },
        },
        "top_run_events": [evt_div.model_dump()],
    }
    (ws / "analysis" / "events.json").write_text(json.dumps(events_data, indent=2))

    # -- analysis/result.json --
    config = ConfigSnapshot(
        case_id="example-case",
        track_ref="dummy_track",
        episode_count=2,
        run_a_world_model_ref="dummy.pth",
        run_b_world_model_ref="dummy.pth",
        adapter_name="dummy",
    )
    result = EvaluationResult(
        config=config,
        episodes_a=episodes_a,
        episodes_b=episodes_b,
        outcomes=outcomes.model_dump(),
        events=events_data,
    )
    (ws / "analysis" / "result.json").write_text(result.model_dump_json(indent=2))

    # -- stage_outputs/compare_report.json --
    (ws / "stage_outputs").mkdir(parents=True, exist_ok=True)
    compare = ComparisonReport(
        baseline_run_dir="dummy.pth",
        candidate_run_dir="dummy.pth",
        metrics=[
            MetricComparison(
                metric_id="final_track_progress",
                baseline_value=0.675,
                candidate_value=0.65,
                delta=-0.025,
                delta_badness=0.037,
                higher_is_better=True,
                significant=True,
                status="regression",
                baseline_per_episode=[0.95, 0.4],
                candidate_per_episode=[1.0, 0.3],
            ),
            MetricComparison(
                metric_id="total_reward",
                baseline_value=3.0,
                candidate_value=3.4,
                delta=0.4,
                delta_badness=-0.133,
                higher_is_better=True,
                significant=False,
                status="improvement",
                baseline_per_episode=[4.5, 1.5],
                candidate_per_episode=[5.7, 1.1],
            ),
        ],
    )
    (ws / "stage_outputs" / "compare_report.json").write_text(
        compare.model_dump_json(indent=2)
    )

    # -- run_state.json --
    run_state = RunState(
        stages={
            "compare": StageState(name="compare", status="completed"),
        }
    )
    (ws / "run_state.json").write_text(run_state.model_dump_json(indent=2))

    # -- attempts/ (empty) --
    (ws / "attempts").mkdir(parents=True, exist_ok=True)

    print(f"Generated: {ws}")


def generate_f1_workspace_draft() -> None:
    ws = ROOT / "f1_demo_workspace_empty"
    ws.mkdir(parents=True, exist_ok=True)

    # -- thesean.toml --
    (ws / "thesean.toml").write_text(
        '[adapter]\ntype = "f1"\nrepo = "/path/to/f1tenth_gym"\n'
    )

    # -- case.json --
    run_a = Run(id="baseline", world_model_ref="dummy.pth", seed=42, horizon=5)
    run_b = Run(id="candidate", world_model_ref="dummy.pth", seed=42, horizon=5)
    case = Case(
        id="empty-case",
        track_ref="dummy_track",
        episode_count=2,
        run_a=run_a,
        run_b=run_b,
    )
    (ws / "case.json").write_text(case.model_dump_json(indent=2))

    # -- workspace_state.json --
    (ws / "workspace_state.json").write_text(
        json.dumps({"case_state": "draft", "attempts": []}, indent=2)
    )

    print(f"Generated: {ws}")


if __name__ == "__main__":
    generate_f1_workspace()
    generate_f1_workspace_draft()
    print("Done.")
