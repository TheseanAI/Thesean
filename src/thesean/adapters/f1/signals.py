"""F1 signal translator — maps raw step data to 13 grouped signals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from thesean.core.signal_schema import LivePairTelemetryView, SignalSchema
    from thesean.pipeline.live_update import LivePairFrame

import math

SIGNAL_GROUPS: dict[str, list[str]] = {
    "Core": ["steering", "throttle", "brake", "speed", "heading"],
    "LiDAR": ["lidar_front", "lidar_left", "lidar_right", "lidar_min"],
    "Derived": ["lap_progress", "offtrack_risk", "reward", "speed_delta"],
}

GROUP_ORDER: list[str] = ["Core", "LiDAR", "Derived"]


# ── Pure heading analysis helpers ──


def _unwrap_heading_window(headings: list[float]) -> list[float]:
    """Unwrap heading values to remove ±π discontinuities."""
    if not headings:
        return []
    unwrapped = [headings[0]]
    for i in range(1, len(headings)):
        delta = headings[i] - headings[i - 1]
        delta = (delta + math.pi) % (2 * math.pi) - math.pi
        unwrapped.append(unwrapped[-1] + delta)
    return unwrapped


def _segment_turn_direction(unwrapped_deltas: list[float]) -> tuple[str, float]:
    """Determine turn direction from unwrapped heading deltas."""
    if not unwrapped_deltas:
        return ("straight", 0.0)
    mean_delta = sum(unwrapped_deltas) / len(unwrapped_deltas)
    if abs(mean_delta) < 0.005:
        return ("straight", mean_delta)
    return ("left" if mean_delta > 0 else "right", mean_delta)


def _segment_curvature_bucket(unwrapped_headings: list[float]) -> tuple[str, float]:
    """Compute curvature proxy from second diff of unwrapped headings."""
    if len(unwrapped_headings) < 3:
        return ("straight", 0.0)
    second_diffs = []
    for i in range(2, len(unwrapped_headings)):
        sd = unwrapped_headings[i] - 2 * unwrapped_headings[i - 1] + unwrapped_headings[i - 2]
        second_diffs.append(abs(sd))
    mean_val = sum(second_diffs) / len(second_diffs)
    if mean_val < 0.005:
        return ("straight", mean_val)
    if mean_val < 0.02:
        return ("gentle", mean_val)
    if mean_val < 0.05:
        return ("moderate", mean_val)
    return ("sharp", mean_val)


class F1SignalTranslator:
    """Translates F1 world model step data into 13 named signals in 3 groups."""

    def signal_names(self) -> list[str]:
        """Return all 13 signal names in group order."""
        names: list[str] = []
        for group in GROUP_ORDER:
            names.extend(SIGNAL_GROUPS[group])
        return names

    def signal_groups(self) -> dict[str, list[str]]:
        """Return mapping of group name to signal name list."""
        return dict(SIGNAL_GROUPS)

    def translate_step(
        self,
        step: dict[str, Any],
        prev_velocity: float | None = None,
    ) -> dict[str, float]:
        """Extract all 13 signals from a raw F1 step dict.

        Returns all 13 keys, using 0.0 for any missing value.
        """
        # ── Core observables (5) ────────────────────────────────────────
        action = step.get("action")
        if action is not None and hasattr(action, "__getitem__") and len(action) >= 3:
            steering = float(action[0])
            throttle = float(action[1])
            brake = float(action[2])
        else:
            steering = 0.0
            throttle = 0.0
            brake = 0.0

        car_state = step.get("car_state", {})
        if isinstance(car_state, dict):
            speed = float(car_state.get("velocity", 0.0))
            heading = float(car_state.get("theta", 0.0))
        else:
            speed = 0.0
            heading = 0.0

        # ── LiDAR summary (4) ──────────────────────────────────────────
        obs = step.get("obs", {})
        aux = obs.get("aux") if isinstance(obs, dict) else None
        if aux is not None and hasattr(aux, "__getitem__") and len(aux) >= 16:
            # aux[0] = speed_norm, aux[1:16] = 15 lidar rays
            lidar_front = (float(aux[7]) + float(aux[8]) + float(aux[9])) / 3.0
            lidar_left = min(float(aux[1]), float(aux[2]), float(aux[3]), float(aux[4]))
            lidar_right = min(float(aux[12]), float(aux[13]), float(aux[14]), float(aux[15]))
            lidar_min = min(float(aux[i]) for i in range(1, 16))
        else:
            lidar_front = 0.0
            lidar_left = 0.0
            lidar_right = 0.0
            lidar_min = 0.0

        # ── Derived racing metrics (4) ─────────────────────────────────
        # CRITICAL: use step["track_progress"], NOT step["info"]["progress"]
        lap_progress = float(step.get("track_progress", 0.0))

        info = step.get("info", {})
        if isinstance(info, dict):
            offtrack_risk = float(info.get("offtrack_steps", 0.0))
        else:
            offtrack_risk = 0.0

        reward = float(step.get("reward", 0.0))

        if prev_velocity is not None:
            speed_delta = speed - prev_velocity
        else:
            speed_delta = 0.0

        return {
            "steering": steering,
            "throttle": throttle,
            "brake": brake,
            "speed": speed,
            "heading": heading,
            "lidar_front": lidar_front,
            "lidar_left": lidar_left,
            "lidar_right": lidar_right,
            "lidar_min": lidar_min,
            "lap_progress": lap_progress,
            "offtrack_risk": offtrack_risk,
            "reward": reward,
            "speed_delta": speed_delta,
        }

    def signal_schema(self) -> SignalSchema:
        """Return structured signal schema with thresholds."""
        from thesean.core.signal_schema import SignalDef, SignalSchema

        _THRESHOLDS: dict[str, float] = {
            "steering": 0.05, "throttle": 0.05, "brake": 0.05,
            "speed": 0.5, "heading": 0.1,
            "lidar_front": 0.05, "lidar_left": 0.05, "lidar_right": 0.05, "lidar_min": 0.05,
            "lap_progress": 0.02, "offtrack_risk": 1.0, "reward": 0.1, "speed_delta": 0.3,
        }
        _LABELS: dict[str, str] = {
            "steering": "Steering", "throttle": "Throttle", "brake": "Brake",
            "speed": "Speed", "heading": "Heading",
            "lidar_front": "LiDAR Front", "lidar_left": "LiDAR Left",
            "lidar_right": "LiDAR Right", "lidar_min": "LiDAR Min",
            "lap_progress": "Lap Progress", "offtrack_risk": "Offtrack Risk",
            "reward": "Reward", "speed_delta": "Speed Delta",
        }
        groups = {}
        for group_name in GROUP_ORDER:
            defs = []
            for name in SIGNAL_GROUPS[group_name]:
                defs.append(SignalDef(
                    name=name,
                    label=_LABELS.get(name, name),
                    delta_threshold=_THRESHOLDS.get(name, 0.1),
                ))
            groups[group_name] = defs
        return SignalSchema(groups=groups, group_order=list(GROUP_ORDER))

    def analyze_segment(
        self,
        signals_a: dict[int, dict[str, float]],
        signals_b: dict[int, dict[str, float]],
        step: int,
        window_half: int = 5,
    ) -> list[tuple[str, str]]:
        """Analyze a local segment around the given step. Returns (label, value) pairs."""
        lo = max(0, step - window_half)
        hi = step + window_half

        # Heading analysis
        headings_a = []
        headings_b = []
        for s in range(lo, hi + 1):
            ha = signals_a.get(s, {}).get("heading")
            hb = signals_b.get(s, {}).get("heading")
            if ha is not None:
                headings_a.append(ha)
            if hb is not None:
                headings_b.append(hb)

        headings = headings_a or headings_b
        lines: list[tuple[str, str]] = []

        if len(headings) >= 2:
            unwrapped = _unwrap_heading_window(headings)
            deltas = [unwrapped[i] - unwrapped[i - 1] for i in range(1, len(unwrapped))]
            direction, mean_delta = _segment_turn_direction(deltas)
            curvature, _ = _segment_curvature_bucket(unwrapped)
            lines.append(("Turn:", f"{direction} (mean Δheading = {mean_delta:+.3f}/step)"))
            lines.append(("Curvature:", curvature))
        else:
            lines.append(("Turn:", "n/a"))
            lines.append(("Curvature:", "n/a"))

        # Boundary margin
        sa = signals_a.get(step, {})
        sb = signals_b.get(step, {})
        margin_a = sa.get("lidar_min")
        margin_b = sb.get("lidar_min")
        ma_str = f"A={margin_a:.2f}" if margin_a is not None else "A=n/a"
        mb_str = f"B={margin_b:.2f}" if margin_b is not None else "B=n/a"
        lines.append(("Boundary margin:", f"{ma_str}  {mb_str}"))

        # Offtrack steps in window
        ot_a = sum(1 for s in range(lo, hi + 1) if signals_a.get(s, {}).get("offtrack_risk", 0) > 0)
        ot_b = sum(1 for s in range(lo, hi + 1) if signals_b.get(s, {}).get("offtrack_risk", 0) > 0)
        lines.append(("Offtrack steps:", f"A={ot_a}     B={ot_b}"))

        # Speed
        speed_a = sa.get("speed")
        speed_b = sb.get("speed")
        if speed_a is not None and speed_b is not None:
            delta = speed_b - speed_a
            sign = "+" if delta >= 0 else ""
            lines.append(("Speed:", f"A={speed_a:.1f}   B={speed_b:.1f}   (Δ={sign}{delta:.1f})"))
        else:
            lines.append(("Speed:", "n/a"))

        # Steering
        steer_a = sa.get("steering")
        steer_b = sb.get("steering")
        if steer_a is not None and steer_b is not None:
            delta = steer_b - steer_a
            sign = "+" if delta >= 0 else ""
            lines.append(("Steering:", f"A={steer_a:+.2f} B={steer_b:+.2f} (Δ={sign}{delta:.2f})"))
        else:
            lines.append(("Steering:", "n/a"))

        # Throttle
        throttle_a = sa.get("throttle")
        throttle_b = sb.get("throttle")
        if throttle_a is not None and throttle_b is not None:
            delta = throttle_b - throttle_a
            sign = "+" if delta >= 0 else ""
            lines.append(("Throttle:", f"A={throttle_a:+.2f} B={throttle_b:+.2f} (Δ={sign}{delta:.2f})"))
        else:
            lines.append(("Throttle:", "n/a"))

        # Brake
        brake_a = sa.get("brake")
        brake_b = sb.get("brake")
        if brake_a is not None and brake_b is not None:
            delta = brake_b - brake_a
            sign = "+" if delta >= 0 else ""
            lines.append(("Brake:", f"A={brake_a:+.2f} B={brake_b:+.2f} (Δ={sign}{delta:.2f})"))
        else:
            lines.append(("Brake:", "n/a"))

        return lines

    @staticmethod
    def _extract_update_rows(update: Any) -> list[tuple[str, str]]:
        if update is None:
            return []
        rows: list[tuple[str, str]] = []
        state = update.state or {}

        rows.append(("Reward:", f"{update.reward:+.2f}"))

        speed = state.get("velocity")
        rows.append(("Speed:", f"{speed:.1f}" if speed is not None else "n/a"))

        action = update.action
        if action and len(action) >= 3:
            rows.append(("Throttle:", f"{action[1]:+.2f}"))

        # LiDAR array: front, left, min, right
        lidar = state.get("lidar")
        if lidar is not None:
            if isinstance(lidar, (list, tuple)) and len(lidar) >= 15:
                front = (lidar[7] + lidar[8] + lidar[9]) / 3.0
                left = min(lidar[1], lidar[2], lidar[3], lidar[4])
                right = min(lidar[12], lidar[13], lidar[14])
                mn = min(lidar[1:])
                rows.append(("LiDAR:", f"F={front:.2f} L={left:.2f} min={mn:.2f} R={right:.2f}"))
            elif isinstance(lidar, (list, tuple)) and lidar:
                margin = min(lidar)
                rows.append(("LiDAR:", f"min={margin:.2f}"))
            elif hasattr(lidar, "min"):
                rows.append(("LiDAR:", f"min={float(lidar.min()):.2f}"))

        return rows

    def format_live_pair(self, frame: LivePairFrame) -> LivePairTelemetryView:
        """Format a LivePairFrame into adapter-specific telemetry view (4C)."""
        from thesean.core.signal_schema import LivePairTelemetryView

        rows_a: list[tuple[str, str]] = []
        rows_b: list[tuple[str, str]] = []
        compare: list[tuple[str, str]] = []

        prog_a = frame.a.progress if frame.a else 0.0
        prog_b = frame.b.progress if frame.b else 0.0

        rows_a = self._extract_update_rows(frame.a)
        rows_b = self._extract_update_rows(frame.b)

        # Deltas
        if frame.a and frame.b:
            dp = prog_b - prog_a
            sign = "+" if dp >= 0 else ""
            compare.append(("Δ Progress:", f"{sign}{dp:.1%}"))

            speed_a = (frame.a.state or {}).get("velocity")
            speed_b = (frame.b.state or {}).get("velocity")
            if speed_a is not None and speed_b is not None:
                ds = speed_b - speed_a
                sign = "+" if ds >= 0 else ""
                compare.append(("Δ Speed:", f"{sign}{ds:.1f}"))

        action_a = list(frame.a.action) if frame.a and frame.a.action else []
        action_b = list(frame.b.action) if frame.b and frame.b.action else []

        return LivePairTelemetryView(
            episode=frame.episode_idx + 1,
            episode_total=frame.episode_total,
            tick=frame.tick,
            rows_a=rows_a, rows_b=rows_b, compare_rows=compare,
            action_a=action_a, action_b=action_b,
            done_a=frame.a.done if frame.a else False,
            done_b=frame.b.done if frame.b else False,
            term_a=frame.a.termination if frame.a else None,
            term_b=frame.b.termination if frame.b else None,
            progress_a=prog_a, progress_b=prog_b,
            max_ticks=frame.max_steps,
        )
