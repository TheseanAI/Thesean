"""Edge case tests for compare_results."""

from __future__ import annotations

import pytest

from thesean.models.episode import EpisodeOutcome, EpisodeRecord
from thesean.pipeline.compare_module import CompareResult, compare_results


def _make_outcome(
    side: str,
    *,
    progress: float = 0.5,
    reward: float = 10.0,
    off_track: float = 0.0,
    fastest_lap: float | None = None,
    n_episodes: int = 1,
) -> tuple[EpisodeOutcome, list[dict]]:
    """Build a minimal EpisodeOutcome and matching raw episode dicts."""
    episodes = [
        EpisodeRecord(
            episode_idx=i,
            final_track_progress=progress,
            total_reward=reward,
            termination=None,
            completed=True,
        )
        for i in range(n_episodes)
    ]
    raw = [
        {"episode_idx": i, "total_reward": reward, "final_track_progress": progress}
        for i in range(n_episodes)
    ]
    outcome = EpisodeOutcome(
        side=side,
        episodes=episodes,
        mean_progress=progress,
        completion_rate=1.0,
        mean_reward=reward,
        off_track_rate=off_track,
        fastest_lap=fastest_lap,
    )
    return outcome, raw


@pytest.mark.unit
def test_compare_with_single_episode() -> None:
    outcome_a, raw_a = _make_outcome("a", progress=0.8, reward=5.0, n_episodes=1)
    outcome_b, raw_b = _make_outcome("b", progress=0.9, reward=6.0, n_episodes=1)

    result = compare_results(outcome_a, outcome_b, raw_a, raw_b)

    assert isinstance(result, CompareResult)
    assert result.verdict in {"regression", "improvement", "no_change", "mixed"}
    assert len(result.metrics) >= 3  # progress, off_track, reward at minimum


@pytest.mark.unit
def test_compare_with_identical_outcomes() -> None:
    outcome_a, raw_a = _make_outcome("a", progress=0.5, reward=10.0)
    outcome_b, raw_b = _make_outcome("b", progress=0.5, reward=10.0)

    result = compare_results(outcome_a, outcome_b, raw_a, raw_b)

    assert result.verdict == "no_change"
    assert result.no_change_count > 0


@pytest.mark.unit
def test_compare_with_zero_baselines() -> None:
    outcome_a, raw_a = _make_outcome(
        "a", progress=0.0, reward=0.0, off_track=0.0, n_episodes=2
    )
    outcome_b, raw_b = _make_outcome(
        "b", progress=0.5, reward=5.0, off_track=0.1, n_episodes=2
    )

    # Should not raise ZeroDivisionError
    result = compare_results(outcome_a, outcome_b, raw_a, raw_b)

    assert isinstance(result, CompareResult)
    # With zero baselines, significance check returns False, so no_change
    assert result.verdict == "no_change"
    assert result.delta_pct == 0.0  # primary baseline is 0 → delta_pct = 0.0
