"""Path-centric context detection for the TUI.

Walks up from cwd to find .thesean/cases/, thesean.toml, or .git boundaries.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_MARKERS = (
    ".git",
    ".thesean",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "CMakeLists.txt",
)


def _project_root_score(path: Path) -> int:
    """Score a directory as a potential project root. 0 = not a project."""
    return sum(1 for m in _PROJECT_MARKERS if (path / m).exists())


def _is_project_root(path: Path) -> bool:
    return _project_root_score(path) > 0


@dataclass
class DetectedContext:
    case: Path | None = None
    project_root: Path | None = None
    cases: list[Path] = field(default_factory=list)
    adapter: str | None = None


def detect_context(
    start: Path, explicit_workspace: Path | None = None
) -> DetectedContext:
    """Resolve launch state from current path."""
    start = start.resolve()

    # 0. Explicit --workspace override always wins
    if explicit_workspace:
        ws = explicit_workspace.resolve()
        if (ws / "thesean.toml").exists():
            pr = _find_project_root(ws)
            return DetectedContext(
                case=ws, project_root=pr,
                adapter=_try_detect_adapter(pr) if pr else None,
            )

    # 1. Current path is a case
    if (start / "thesean.toml").exists():
        pr = _find_project_root(start)
        return DetectedContext(
            case=start, project_root=pr,
            adapter=_try_detect_adapter(pr) if pr else None,
        )

    # 2. Current path is inside a case dir (parent has thesean.toml)
    for parent in start.parents:
        if (parent / "thesean.toml").exists():
            pr = _find_project_root(parent)
            return DetectedContext(
                case=parent, project_root=pr,
                adapter=_try_detect_adapter(pr) if pr else None,
            )
        if (parent / ".thesean").is_dir() or _is_project_root(parent):
            break

    # 3. Current path is inside a repo that owns .thesean/cases/
    for check in [start, *start.parents]:
        thesean_dir = check / ".thesean"
        if thesean_dir.is_dir():
            cases = _list_cases(thesean_dir / "cases")
            return DetectedContext(
                project_root=check,
                cases=cases,
                adapter=_try_detect_adapter(check),
            )
        if _is_project_root(check):
            return DetectedContext(
                project_root=check,
                adapter=_try_detect_adapter(check),
            )

    # 4. Nothing found
    return DetectedContext()


def _find_project_root(start: Path) -> Path | None:
    """Walk up from start to find a project root by marker score."""
    for check in [start, *start.parents]:
        if _is_project_root(check):
            return check
    return None


def _list_cases(cases_dir: Path) -> list[Path]:
    """List valid case directories sorted by mtime (most recent first)."""
    if not cases_dir.is_dir():
        return []
    cases: list[Path] = []
    for child in cases_dir.iterdir():
        if child.is_dir() and ((child / "thesean.toml").exists() or (child / "case.json").exists()):
            cases.append(child)
    cases.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cases


def _try_detect_adapter(project_root: Path) -> str | None:
    """Best-effort adapter detection from project structure."""
    # Check for common adapter markers
    if (project_root / "f1_adapter.py").exists():
        return "f1"
    # Check for F1 repo structure (checkpoints/ + tracks/)
    if (project_root / "checkpoints").is_dir() and (project_root / "tracks").is_dir():
        return "f1"
    if (project_root / "pyproject.toml").exists():
        try:
            text = (project_root / "pyproject.toml").read_text()
            if "thesean" in text and "adapter" in text:
                # Very basic heuristic
                for line in text.splitlines():
                    if "adapter" in line and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except OSError:
            pass
    # Try registered adapters to see if any can discover content
    try:
        from thesean.adapters.registry import discover_adapter_factories
        for name, factory_cls in discover_adapter_factories().items():
            try:
                factory = factory_cls()
                factory.bind_repo(project_root)
                if factory.discover_weights(project_root):
                    return name
            except Exception:
                continue
    except Exception:
        pass
    return None


# ── Recent cases persistence ──


def _migrate_app_dir(new_dir: Path) -> None:
    """Rename old Application Support dirs (TheSean, Thesean) → thesean."""
    if new_dir.exists():
        return
    for old_name in ("TheSean", "Thesean"):
        old_dir = new_dir.parent / old_name
        if old_dir.is_dir():
            try:
                old_dir.rename(new_dir)
            except OSError:
                pass
            return


def _recent_cases_path() -> Path:
    """Platform-aware path for recent cases file."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "thesean"
    elif sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming" / "thesean"
    else:
        base = Path.home() / ".local" / "share" / "thesean"
    _migrate_app_dir(base)
    return base / "recent.json"


@dataclass
class RecentCase:
    project: str
    case: str
    last_opened: str


def load_recent_cases() -> list[RecentCase]:
    """Load recent cases from platform-aware storage."""
    path = _recent_cases_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [
            RecentCase(
                project=entry.get("project", ""),
                case=entry.get("case", ""),
                last_opened=entry.get("last_opened", ""),
            )
            for entry in data
            if isinstance(entry, dict)
        ]
    except (json.JSONDecodeError, OSError):
        return []


def save_recent_case(project: Path | None, case_path: Path) -> None:
    """Record a case open in recent cases."""
    try:
        path = _recent_cases_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        recents = load_recent_cases()

        case_name = case_path.name
        project_str = str(project) if project else ""

        # Remove existing entry for this case
        recents = [
            r
            for r in recents
            if not (r.project == project_str and r.case == case_name)
        ]

        # Prepend new entry
        recents.insert(
            0,
            RecentCase(
                project=project_str,
                case=case_name,
                last_opened=datetime.now(tz=timezone.utc).isoformat(),
            ),
        )

        # Keep only last 20
        recents = recents[:20]

        data = [
            {
                "project": r.project,
                "case": r.case,
                "last_opened": r.last_opened,
            }
            for r in recents
        ]
        path.write_text(json.dumps(data, indent=2))
    except OSError:
        pass
