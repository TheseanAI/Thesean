"""Bridge between TUI and existing backend — all methods are synchronous (called from Workers)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from thesean.models.case import Case

from thesean.cli.wizard.discovery import (
    discover_adapters as _discover_adapters,
)
from thesean.cli.wizard.discovery import (
    discover_envs as _discover_envs,
)
from thesean.cli.wizard.discovery import (
    discover_weights as _discover_weights,
)
from thesean.cli.wizard.discovery import (
    get_env_config as _get_env_config,
)
from thesean.cli.wizard.discovery import (
    get_planner_defaults as _get_planner_defaults,
)
from thesean.cli.wizard.discovery import (
    load_factory,
)
from thesean.models.comparison import ComparisonReport
from thesean.models.episode import (
    METRIC_DISPLAY_NAMES,
    OutcomeSummary,
)
from thesean.models.evaluation_result import ConfigSnapshot, EvaluationResult
from thesean.models.isolation import AttributionTable, EffectEstimate, IsolationResultBundle
from thesean.pipeline.compare_module import CompareResult, build_episode_outcome, compare_results
from thesean.pipeline.context import RunContext
from thesean.pipeline.runner import StageObserver, run_stages
from thesean.pipeline.stages import DEFAULT_PIPELINE
from thesean.pipeline.workspace import (
    create_workspace_dirs,
    read_workspace_state,
    save_episodes,
    update_case_state,
    write_workspace_state,
)
from thesean.reporting.bundle import build_report_bundle
from thesean.reporting.types import ReportBundle


class TuiBackendService:
    # ── Workspace loading ──

    def load_workspace_bundle(self, workspace: Path) -> ReportBundle:
        return build_report_bundle(workspace)

    def load_compare_report(self, workspace: Path) -> ComparisonReport | None:
        path = workspace / "stage_outputs" / "compare_report.json"
        if not path.exists():
            return None
        return ComparisonReport.model_validate_json(path.read_text())

    def load_isolation_bundle(self, workspace: Path) -> IsolationResultBundle | None:
        path = workspace / "stage_outputs" / "isolate.json"
        if not path.exists():
            return None
        return IsolationResultBundle.model_validate_json(path.read_text())

    def load_attributions(self, workspace: Path) -> list[AttributionTable]:
        from pydantic import TypeAdapter
        path = workspace / "stage_outputs" / "attribute.json"
        if not path.exists():
            return []
        adapter = TypeAdapter(list[AttributionTable])
        return adapter.validate_json(path.read_text())

    # ── Discovery ──

    def discover_adapters(self) -> list[str]:
        return _discover_adapters()

    def discover_weights(self, adapter_name: str, repo: Path) -> list[dict[str, Any]]:
        factory = load_factory(adapter_name)
        factory.bind_repo(repo)
        return _discover_weights(factory, repo)

    def discover_envs(self, adapter_name: str, repo: Path) -> list[str]:
        factory = load_factory(adapter_name)
        factory.bind_repo(repo)
        return _discover_envs(factory, repo)

    def default_planner_config(self, adapter_name: str, repo: Path) -> dict[str, Any]:
        factory = load_factory(adapter_name)
        factory.bind_repo(repo)
        return _get_planner_defaults(factory)

    def default_env_config(self, adapter_name: str, repo: Path, env_id: str) -> dict[str, Any]:
        factory = load_factory(adapter_name)
        factory.bind_repo(repo)
        return _get_env_config(factory, env_id)

    def discover_controllers(self, adapter_name: str, repo: Path) -> list[dict[str, Any]]:
        factory = load_factory(adapter_name)
        factory.bind_repo(repo)
        if hasattr(factory, "discover_controllers"):
            return factory.discover_controllers()  # type: ignore[no-any-return]
        return []

    # ── Workspace ──

    def create_workspace(self, workspace: Path, case: Case, adapter_name: str, repo: Path) -> None:
        """Create a durable workspace directory with frozen case definition (D-01).

        Creates directory structure, writes case.json + thesean.toml + workspace_state.json.
        """
        create_workspace_dirs(workspace)
        self.create_case(workspace, case)
        self.write_workspace_config(workspace, adapter_name, repo)
        write_workspace_state(workspace, {"case_state": "draft", "attempts": []})

    def load_workspace_state(self, workspace: Path) -> dict[str, Any]:
        """Load workspace_state.json for case state info."""
        return read_workspace_state(workspace)

    # ── Case & Project ──

    def create_case(self, workspace: Path, case: Case) -> Path:
        """Write a Case to the workspace."""
        from thesean.pipeline.case_io import save_case
        return save_case(case, workspace)

    def load_case(self, workspace: Path) -> Case | None:
        """Load a Case from the workspace."""
        from thesean.pipeline.case_io import load_case
        return load_case(workspace)

    def discover_project(self, adapter_name: str, repo: Path) -> dict[str, Any]:
        """Use adapter's detect_project if available."""
        factory = load_factory(adapter_name)
        factory.bind_repo(repo)
        if hasattr(factory, "detect_project"):
            return factory.detect_project(repo)
        return {"weights": self.discover_weights(adapter_name, repo), "envs": self.discover_envs(adapter_name, repo)}

    def load_events(self, workspace: Path, episode_id: str | None = None) -> list:
        """Load events from analysis/events.json.

        If episode_id is provided, loads events for that episode.
        Otherwise loads top_run_events (default view).
        Falls back to legacy flat-list format.
        """
        from thesean.models.event import Event
        path = workspace / "analysis" / "events.json"
        if not path.exists():
            path = workspace / "stage_outputs" / "events.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())

        # New structure with events_by_episode
        if isinstance(data, dict) and "top_run_events" in data:
            if episode_id and "events_by_episode" in data:
                for side in ("a", "b"):
                    side_events = data["events_by_episode"].get(side, {})
                    if episode_id in side_events:
                        return [Event.model_validate(e) for e in side_events[episode_id]]
                return []
            return [Event.model_validate(e) for e in data["top_run_events"]]

        # Legacy flat list
        if isinstance(data, list):
            return [Event.model_validate(e) for e in data]
        return []

    def load_events_by_episode(self, workspace: Path) -> dict[str, list]:
        """Load events grouped by episode_id. Returns {ep_id: [Event, ...]}.

        If events.json is missing but episode data exists, extracts events
        on the fly and writes events.json for next time.
        """
        from thesean.models.event import Event
        path = workspace / "analysis" / "events.json"

        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, dict) and "events_by_episode" in data:
                result = {}
                for ep_id, raw_events in data["events_by_episode"].get("a", {}).items():
                    result[ep_id] = [Event.model_validate(e) for e in raw_events]
                return result

        # No events.json — try to extract from episode data
        return self._extract_and_cache_events(workspace)

    def _extract_and_cache_events(self, workspace: Path) -> dict[str, list]:
        """Extract events from saved episodes and write events.json."""
        from thesean.pipeline.event_extraction import extract_events_for_episode

        eps_a_path = workspace / "runs" / "a" / "episodes.json"
        eps_b_path = workspace / "runs" / "b" / "episodes.json"
        if not eps_a_path.exists() or not eps_b_path.exists():
            return {}

        translator = self._resolve_translator_from_workspace(workspace)
        if translator is None:
            return {}

        try:
            raw_a = json.loads(eps_a_path.read_text())
            raw_b = json.loads(eps_b_path.read_text())
            n_eps = min(len(raw_a), len(raw_b))

            events_by_episode: dict[str, dict[str, list]] = {"a": {}, "b": {}}
            result: dict[str, list] = {}

            for i in range(n_eps):
                ep_id = f"ep_{i:04d}"
                steps_a = raw_a[i].get("steps", [])
                steps_b = raw_b[i].get("steps", [])
                ep_events = extract_events_for_episode(steps_a, steps_b, ep_id, translator=translator)
                serialized = [e.model_dump() for e in ep_events]
                events_by_episode["a"][ep_id] = serialized
                events_by_episode["b"][ep_id] = serialized
                result[ep_id] = ep_events

            # Cache to disk
            analysis_dir = workspace / "analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            events_path = analysis_dir / "events.json"
            events_path.write_text(json.dumps({
                "events_by_episode": events_by_episode,
                "top_run_events": [],
            }, indent=2))

            return result
        except Exception:
            return {}

    def load_outcomes(self, workspace: Path) -> OutcomeSummary | None:
        """Load analysis/outcomes.json if it exists."""
        path = workspace / "analysis" / "outcomes.json"
        if not path.exists():
            return None
        return OutcomeSummary.model_validate_json(path.read_text())

    def load_result(self, workspace: Path) -> EvaluationResult | None:
        """Load analysis/result.json as typed EvaluationResult."""
        path = workspace / "analysis" / "result.json"
        if not path.exists():
            return None
        return EvaluationResult.model_validate_json(path.read_text())

    def load_episode_signals(
        self,
        workspace: Path,
        side: str,
        episode_idx: int,
        translator: Any = None,
    ) -> dict[int, dict[str, float]]:
        """Load per-step signals for one episode from episodes.json.

        Returns: {step_idx: {signal_name: value}} for all steps in the episode.
        Loads only the requested episode (not all episodes) to keep memory low.
        """
        path = workspace / "runs" / side / "episodes.json"
        if not path.exists():
            return {}
        raw_episodes = json.loads(path.read_text())
        if episode_idx >= len(raw_episodes):
            return {}

        if translator is None:
            translator = self._resolve_translator_from_workspace(workspace)
        if translator is None:
            return {}

        ep = raw_episodes[episode_idx]
        steps = ep.get("steps", [])
        signals: dict[int, dict[str, float]] = {}
        prev_velocity: float | None = None
        for i, step in enumerate(steps):
            translated = translator.translate_step(step)
            # Compute speed_delta from consecutive velocities
            velocity = 0.0
            car_state = step.get("car_state", {})
            if isinstance(car_state, dict):
                velocity = float(car_state.get("velocity", 0.0))
            if prev_velocity is not None:
                translated["speed_delta"] = velocity - prev_velocity
            prev_velocity = velocity
            signals[i] = translated
        return signals

    def get_episode_count(self, workspace: Path, side: str = "a") -> int:
        """Return number of episodes for a side."""
        path = workspace / "runs" / side / "episodes.json"
        if not path.exists():
            return 0
        raw = json.loads(path.read_text())
        return len(raw) if isinstance(raw, list) else 0

    # ── Case listing ──

    def list_cases(self, project_root: Path) -> list[Path]:
        """List valid case directories under .thesean/cases/."""
        cases_dir = project_root / ".thesean" / "cases"
        if not cases_dir.is_dir():
            return []
        cases: list[Path] = []
        for child in sorted(cases_dir.iterdir()):
            if child.is_dir() and ((child / "thesean.toml").exists() or (child / "case.json").exists()):
                cases.append(child)
        return cases

    # ── Workspace config ──

    def write_workspace_config(self, workspace: Path, adapter_name: str, repo: Path) -> None:
        """Write thesean.toml to workspace so detection and RunContext can find it."""
        import tomli_w

        config = {
            "adapter": {"type": adapter_name, "repo": str(repo)},
            "run": {},
            "event": {},
        }
        (workspace / "thesean.toml").write_text(tomli_w.dumps(config))

    # ── Pipeline execution ──

    def run_full_pipeline(self, workspace: Path, observer: StageObserver | None = None) -> None:
        pipeline_names = tuple(s.name for s in DEFAULT_PIPELINE)
        ctx = RunContext(workspace, pipeline_names=pipeline_names)
        run_stages(ctx, DEFAULT_PIPELINE, observer=observer)  # type: ignore[arg-type]

    def run_compare_only(self, workspace: Path, observer: StageObserver | None = None) -> None:
        from thesean.pipeline.stages import CompareStage
        stages = (CompareStage(),)
        pipeline_names = tuple(s.name for s in stages)
        ctx = RunContext(workspace, pipeline_names=pipeline_names)
        run_stages(ctx, stages, observer=observer)  # type: ignore[arg-type]

    def run_isolate_only(self, workspace: Path, observer: StageObserver | None = None) -> None:
        from thesean.pipeline.stages import AttributeStage, IsolateStage
        stages = (IsolateStage(), AttributeStage())
        pipeline_names = tuple(s.name for s in DEFAULT_PIPELINE)
        ctx = RunContext(workspace, pipeline_names=pipeline_names)
        # Synthesize completed state for prerequisite stages (artifacts already exist)
        ctx.mark_reused("compare")
        ctx.mark_reused("events")
        ctx.save_state()
        run_stages(ctx, stages, observer=observer)  # type: ignore[arg-type]

    def run_report_only(self, workspace: Path, observer: StageObserver | None = None) -> None:
        from thesean.pipeline.stages import ReportStage
        stages = (ReportStage(),)
        pipeline_names = tuple(s.name for s in DEFAULT_PIPELINE)
        ctx = RunContext(workspace, pipeline_names=pipeline_names)
        run_stages(ctx, stages, observer=observer)  # type: ignore[arg-type]

    # ── Evaluation ──

    def _resolve_translator_from_workspace(self, workspace: Path) -> Any:
        """Resolve a SignalTranslator from workspace thesean.toml config."""
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        toml_path = workspace / "thesean.toml"
        if not toml_path.exists():
            return None
        try:
            config = tomllib.loads(toml_path.read_text())
            adapter_type = config.get("adapter", {}).get("type")
            repo = config.get("adapter", {}).get("repo")
            if not adapter_type or not repo:
                return None
            from thesean.cli.wizard.discovery import load_factory
            factory = load_factory(adapter_type)
            factory.bind_repo(Path(repo))
            if hasattr(factory, "get_signal_translator"):
                return factory.get_signal_translator()
        except Exception:
            return None
        return None

    def run_evaluation(
        self,
        workspace: Path,
        case: Case,
        adapter_name: str,
        repo: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
        live_sink: Callable[..., None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Run A vs B evaluation in lockstep, saving episodes to workspace (D-19, 4C).

        Args:
            workspace: Path to case workspace directory
            case: Case with run_a, run_b, track_ref, episode_count, eval_seeds
            adapter_name: Adapter type name (e.g. "f1")
            repo: Path to adapter repo (e.g. f1worldmodel-main)
            progress_callback: Called with (side_label, current_episode, total_episodes)
                for progress updates
            live_sink: Called with LivePairFrame for real-time pair telemetry (4C)

        Raises:
            Exception: On any failure. Caller is responsible for catching and
                recording failure metadata via save_failed_attempt().
        """
        from thesean.pipeline.paired_runner import run_paired_episodes

        if not case.track_ref:
            raise ValueError("No track selected — choose a track in the case builder before running")

        factory = load_factory(adapter_name)
        factory.bind_repo(repo)

        seeds = case.eval_seeds or list(range(case.episode_count))

        if case.run_a is None or case.run_b is None:
            raise ValueError("Both run_a and run_b must be specified for paired evaluation")

        # Create world models and planners for both sides
        wm_a = factory.create_world_model(case.run_a.world_model_ref)
        planner_a = factory.create_planner(dict(case.run_a.planner_config), wm_a)
        wm_b = factory.create_world_model(case.run_b.world_model_ref)
        planner_b = factory.create_planner(dict(case.run_b.planner_config), wm_b)

        # Build env configs with raster_size inferred from world model checkpoints
        env_config_a = factory.default_env_config(case.track_ref, world_model=wm_a)
        env_config_b = factory.default_env_config(case.track_ref, world_model=wm_b)
        if case.shared_env_overrides:
            env_config_a.update(case.shared_env_overrides)
            env_config_b.update(case.shared_env_overrides)

        # Run paired episodes
        all_episodes_a: list[dict] = []
        all_episodes_b: list[dict] = []

        for ep_idx in range(case.episode_count):
            if progress_callback:
                progress_callback("ab", ep_idx + 1, case.episode_count)

            ep_seed = seeds[ep_idx] if ep_idx < len(seeds) else seeds[0] + ep_idx

            env_a = factory.create_env(env_config_a)
            env_b = factory.create_env(env_config_b)

            eps_a, eps_b = run_paired_episodes(
                env_a, env_b, planner_a, planner_b,
                num_episodes=1, seed=ep_seed,
                pair_callback=live_sink,
                max_steps=env_config_a.get("max_steps", 0),
                cancel_event=cancel_event,
            )
            all_episodes_a.extend(eps_a)
            all_episodes_b.extend(eps_b)

        save_episodes(workspace, "a", all_episodes_a)
        save_episodes(workspace, "b", all_episodes_b)
        update_case_state(workspace, "ready")

    def run_analysis(self, workspace: Path, translator: Any = None) -> OutcomeSummary:
        """Compute outcomes from saved episode data and write analysis/outcomes.json (D-15, D-16).

        Reads runs/a/episodes.json and runs/b/episodes.json.
        Writes analysis/outcomes.json.
        On failure: does NOT update case_state (caller handles D-17).

        Returns OutcomeSummary for immediate use by the TUI.
        Raises on any failure.
        """
        # Resolve translator from workspace config if not provided
        if translator is None:
            translator = self._resolve_translator_from_workspace(workspace)

        # 1. Load raw episode dicts for each side
        def _load_side_episodes(ws: Path, side: str) -> list[dict]:
            path = ws / "runs" / side / "episodes.json"
            if not path.exists():
                raise FileNotFoundError(f"Episode data not found: {path}")
            return json.loads(path.read_text())  # type: ignore[no-any-return]

        raw_a = _load_side_episodes(workspace, "a")
        raw_b = _load_side_episodes(workspace, "b")

        # 2. Build typed outcomes and run comparison via compare_module
        outcome_a = build_episode_outcome("a", raw_a)
        outcome_b = build_episode_outcome("b", raw_b)
        result = compare_results(outcome_a, outcome_b, raw_a, raw_b)

        # 3. Build display strings from CompareResult (presentation stays here per D-01)
        def _build_headline(r: CompareResult) -> str:
            if r.verdict == "no_change":
                return "No significant difference detected between baseline and candidate."
            if r.verdict == "mixed":
                return "Mixed results — candidate shows regressions and improvements."

            if r.verdict == "regression":
                agreeing = sorted(
                    [m for m in r.metrics if m.significant and m.status == "regression"],
                    key=lambda m: m.delta_badness,
                    reverse=True,
                )
                base_line = "Candidate underperformed baseline under the same planner setup."
            else:  # improvement
                agreeing = sorted(
                    [m for m in r.metrics if m.significant and m.status == "improvement"],
                    key=lambda m: m.delta_badness,
                )
                base_line = "Candidate outperformed baseline under the same planner setup."

            if len(agreeing) < 2:
                return base_line

            phrases: list[str] = []
            for m in agreeing[:3]:
                display = METRIC_DISPLAY_NAMES.get(m.metric_id, m.metric_id.replace("_", " "))
                if m.higher_is_better and m.delta_badness > 0:
                    phrase = f"lower {display}"
                elif not m.higher_is_better and m.delta_badness > 0 or m.higher_is_better and m.delta_badness < 0:
                    phrase = f"higher {display}"
                else:
                    phrase = f"lower {display}"
                phrases.append(phrase)

            if len(phrases) == 1:
                joined = phrases[0]
            elif len(phrases) == 2:
                joined = f"{phrases[0]} and {phrases[1]}"
            else:
                joined = f"{', '.join(phrases[:-1])}, and {phrases[-1]}"

            base = base_line.rstrip(".")
            return f"{base} — {joined}."

        def _fmt_value(metric_id: str, value: float) -> str:
            if metric_id in ("final_track_progress", "off_track_rate"):
                return f"{value:.0%}"
            elif metric_id == "fastest_lap_time":
                return f"{value:.1f}s"
            else:
                return f"{value:.1f}"

        verdict_headline = _build_headline(result)

        fmt_candidate = _fmt_value(result.primary_metric, result.candidate_value)
        fmt_baseline = _fmt_value(result.primary_metric, result.baseline_value)
        primary_metric_line = (
            f"{result.primary_metric_display}: candidate {fmt_candidate} "
            f"vs baseline {fmt_baseline} ({result.delta_pct:+.1f}%)"
        )

        r = result.regression_count
        i = result.improvement_count
        if r > 0 and i > 0:
            findings_count_line = (
                f"{r} {'metric' if r == 1 else 'metrics'} regressed, {i} improved"
            )
        elif r > 0:
            findings_count_line = f"{r} {'metric' if r == 1 else 'metrics'} regressed"
        elif i > 0:
            findings_count_line = f"{i} {'metric' if i == 1 else 'metrics'} improved"
        else:
            findings_count_line = "No significant findings"

        # 4. Construct OutcomeSummary combining CompareResult + display strings
        n_eps = min(len(raw_a), len(raw_b))
        outcomes = OutcomeSummary(
            verdict=result.verdict,
            primary_metric=result.primary_metric,
            primary_metric_display=result.primary_metric_display,
            baseline_value=result.baseline_value,
            candidate_value=result.candidate_value,
            delta_pct=result.delta_pct,
            significant=result.significant,
            regression_count=result.regression_count,
            improvement_count=result.improvement_count,
            no_change_count=result.no_change_count,
            verdict_headline=verdict_headline,
            primary_metric_line=primary_metric_line,
            findings_count_line=findings_count_line,
            top_run=result.top_run,
            recommended_run_ids=result.recommended_run_ids,
            episodes_a=outcome_a.episodes,
            episodes_b=outcome_b.episodes,
        )
        outcomes_path = workspace / "analysis" / "outcomes.json"
        outcomes_path.write_text(outcomes.model_dump_json(indent=2))

        # 8. Event extraction — write analysis/events.json
        events_data = None
        try:
            from thesean.pipeline.event_extraction import extract_events_for_episode

            events_by_episode: dict[str, dict[str, list]] = {"a": {}, "b": {}}
            for i in range(n_eps):
                ep_id_i = f"ep_{i:04d}"
                steps_a_list = raw_a[i].get("steps", [])
                steps_b_list = raw_b[i].get("steps", [])
                ep_events = extract_events_for_episode(steps_a_list, steps_b_list, ep_id_i, translator=translator)
                serialized = [e.model_dump() for e in ep_events]
                events_by_episode["a"][ep_id_i] = serialized
                events_by_episode["b"][ep_id_i] = serialized

            top_run_ep_id = result.top_run["episode_id"] if result.top_run else "ep_0000"
            top_run_events = events_by_episode.get("a", {}).get(top_run_ep_id, [])

            events_data = {
                "events_by_episode": events_by_episode,
                "top_run_events": top_run_events,
            }
            events_path = workspace / "analysis" / "events.json"
            events_path.write_text(json.dumps(events_data, indent=2))
        except Exception as exc:
            import logging
            logging.getLogger("thesean.pipeline").warning("Event extraction failed: %s", exc)

        # 9. Write stage_outputs so attribution screen has data
        try:
            from thesean.models.comparison import MetricComparison

            stage_dir = workspace / "stage_outputs"
            stage_dir.mkdir(parents=True, exist_ok=True)

            # Extract per-episode metric values from raw episode dicts
            def _extract_per_episode(raw_eps: list[dict], metric_id: str) -> list[float]:
                values = []
                for ep in raw_eps:
                    if metric_id == "total_reward":
                        values.append(float(ep.get("total_reward", 0.0)))
                    elif metric_id == "final_track_progress":
                        values.append(float(ep.get("final_track_progress", 0.0)))
                    elif metric_id == "off_track_rate":
                        term = ep.get("termination")
                        values.append(1.0 if term == "off_track" else 0.0)
                    elif metric_id == "fastest_lap_time":
                        values.append(float(ep.get("fastest_lap_time", 0.0) or 0.0))
                    else:
                        values.append(0.0)
                return values

            # Build ComparisonReport from CompareResult
            compare_metrics = []
            for m in result.metrics:
                compare_metrics.append(MetricComparison(
                    metric_id=m.metric_id,
                    baseline_value=m.baseline_value,
                    candidate_value=m.candidate_value,
                    delta=m.delta,
                    delta_badness=m.delta_badness,
                    higher_is_better=m.higher_is_better,
                    significant=m.significant,
                    status=m.status,
                    baseline_per_episode=_extract_per_episode(raw_a, m.metric_id),
                    candidate_per_episode=_extract_per_episode(raw_b, m.metric_id),
                ))
            case_data_for_report = json.loads(
                (workspace / "case.json").read_text()
            ) if (workspace / "case.json").exists() else {}
            compare_report = ComparisonReport(
                baseline_run_dir=case_data_for_report.get("run_a", {}).get("world_model_ref", "a"),
                candidate_run_dir=case_data_for_report.get("run_b", {}).get("world_model_ref", "b"),
                metrics=compare_metrics,
            )
            (stage_dir / "compare_report.json").write_text(
                compare_report.model_dump_json(indent=2)
            )

            # Build basic AttributionTable from regression metrics
            regressions = [m for m in result.metrics if m.status == "regression"]
            attr_tables: list[AttributionTable] = []
            for m in regressions:
                effects = [EffectEstimate(
                    factor=m.metric_id,
                    effect=m.delta_badness,
                    confidence=0.8 if m.significant else 0.4,
                )]
                attr_tables.append(AttributionTable(
                    metric_id=m.metric_id,
                    main_effects=effects,
                    decision="unknown",
                ))
            (stage_dir / "attribute.json").write_text(
                json.dumps([t.model_dump() for t in attr_tables], indent=2)
            )
        except Exception:
            pass  # stage_outputs are supplementary

        # 10. Save EvaluationResult snapshot — last action before return
        try:
            case_json_path = workspace / "case.json"
            case_data = json.loads(case_json_path.read_text()) if case_json_path.exists() else {}
            config = ConfigSnapshot(
                case_id=case_data.get("id", ""),
                track_ref=case_data.get("track_ref", ""),
                episode_count=case_data.get("episode_count", 0),
                eval_seeds=case_data.get("eval_seeds"),
                run_a_world_model_ref=case_data.get("run_a", {}).get("world_model_ref", ""),
                run_b_world_model_ref=case_data.get("run_b", {}).get("world_model_ref", ""),
                run_a_planner_ref=case_data.get("run_a", {}).get("planner_ref", ""),
                run_b_planner_ref=case_data.get("run_b", {}).get("planner_ref", ""),
            )
            eval_result = EvaluationResult(
                config=config,
                episodes_a=raw_a,
                episodes_b=raw_b,
                outcomes=outcomes.model_dump(),
                events=events_data,
            )
            result_path = workspace / "analysis" / "result.json"
            result_path.write_text(eval_result.model_dump_json(indent=2))
        except Exception:
            pass  # result.json is supplementary — don't fail the analysis pipeline

        return outcomes

    # ── Report generation ──

    def generate_report_from_artifacts(self, workspace: Path) -> Path:
        """Generate HTML report from saved analysis/result.json only (COMP-04).

        Single canonical source: analysis/result.json contains EvaluationResult
        which bundles config, episodes, and outcomes. No dual-file loading.
        """
        from jinja2 import Environment, FileSystemLoader

        result_path = workspace / "analysis" / "result.json"
        if not result_path.exists():
            raise FileNotFoundError("No saved results found")

        result = EvaluationResult.model_validate_json(result_path.read_text())
        outcomes = OutcomeSummary.model_validate(result.outcomes)

        template_dir = files("thesean.reporting") / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        template = env.get_template("investigation_report.html.j2")

        html = template.render(
            outcomes=outcomes,
            config=result.config,
            created_at=result.created_at,
        )

        out = workspace / "report.html"
        out.write_text(html)
        return out

    # ── Artifacts ──

    def read_artifact_text(self, path: Path) -> str:
        try:
            text = path.read_text()
            try:
                data = json.loads(text)
                return json.dumps(data, indent=2)
            except (json.JSONDecodeError, ValueError):
                return text
        except Exception as e:
            return f"Error reading file: {e}"
