"""Signal schema — adapter-agnostic signal definitions for TUI widgets."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SignalDef:
    name: str
    label: str                    # human-readable ("Steering", "LiDAR Min")
    format: str = ".3f"           # Python format spec
    delta_threshold: float = 0.1  # threshold for "significant" highlighting


@dataclass(frozen=True)
class SignalSchema:
    groups: dict[str, list[SignalDef]]  # group_name -> signal defs
    group_order: list[str]              # display ordering of groups

    def signal_names(self) -> list[str]:
        return [d.name for g in self.group_order for d in self.groups.get(g, [])]

    def get_def(self, name: str) -> SignalDef | None:
        for defs in self.groups.values():
            for d in defs:
                if d.name == name:
                    return d
        return None

    def delta_threshold(self, name: str) -> float:
        d = self.get_def(name)
        return d.delta_threshold if d else 0.1


@dataclass(frozen=True)
class LivePairTelemetryView:
    """Adapter-formatted pair telemetry view for TUI consumption."""

    episode: int
    episode_total: int
    tick: int
    rows_a: list[tuple[str, str]] = field(default_factory=list)
    rows_b: list[tuple[str, str]] = field(default_factory=list)
    compare_rows: list[tuple[str, str]] = field(default_factory=list)
    action_a: list[float] = field(default_factory=list)
    action_b: list[float] = field(default_factory=list)
    done_a: bool = False
    done_b: bool = False
    term_a: str | None = None
    term_b: str | None = None
    progress_a: float = 0.0
    progress_b: float = 0.0
    max_ticks: int = 0
