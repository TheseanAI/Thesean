"""Shared TUI test helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from thesean.tui.detection import DetectedContext

# ── Example workspace fixtures ──

def _project_root() -> Path:
    """Resolve thesean project root (contains pyproject.toml)."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Cannot find project root")


@pytest.fixture()
def example_workspace() -> Path:
    """Path to the fully populated F1 workspace."""
    ws = _project_root() / "examples" / "f1_demo_workspace"
    assert ws.exists(), f"Missing example workspace: {ws}"
    return ws


@pytest.fixture()
def empty_workspace() -> Path:
    """Path to the minimal draft F1 workspace (no runs/analysis)."""
    ws = _project_root() / "examples" / "f1_demo_workspace_empty"
    assert ws.exists(), f"Missing empty workspace: {ws}"
    return ws


# ── Patched app fixtures ──

@pytest.fixture()
def patched_app(example_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """TheSeanApp pointed at the F1 workspace with adapter loading stubbed."""
    from thesean.tui.app import TheSeanApp
    from tests.conftest import DummyAdapterFactory

    factory = DummyAdapterFactory()

    monkeypatch.setattr(
        "thesean.pipeline.context.load_adapter_factory",
        lambda name: factory,
    )
    monkeypatch.setattr(
        "thesean.tui.detection.detect_context",
        lambda start, explicit_workspace=None: DetectedContext(
            case=example_workspace,
            project_root=example_workspace,
            adapter="dummy",
        ),
    )
    monkeypatch.setattr(
        "thesean.cli.wizard.discovery.load_factory",
        lambda name: factory,
    )

    return TheSeanApp(explicit_workspace=example_workspace)


@pytest.fixture()
def patched_empty_app(empty_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """TheSeanApp pointed at the draft F1 workspace."""
    from thesean.tui.app import TheSeanApp
    from tests.conftest import DummyAdapterFactory

    factory = DummyAdapterFactory()

    monkeypatch.setattr(
        "thesean.pipeline.context.load_adapter_factory",
        lambda name: factory,
    )
    monkeypatch.setattr(
        "thesean.tui.detection.detect_context",
        lambda start, explicit_workspace=None: DetectedContext(
            case=empty_workspace,
            project_root=empty_workspace,
            adapter="dummy",
        ),
    )
    monkeypatch.setattr(
        "thesean.cli.wizard.discovery.load_factory",
        lambda name: factory,
    )

    return TheSeanApp(explicit_workspace=empty_workspace)
