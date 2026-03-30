"""Pilot-driven TUI integration tests — exercise real app + adapter via example workspace."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.tui]


def _static_text(widget) -> str:
    """Extract text from a Static widget across Textual versions."""
    # Name-mangled __content from Static.update()
    content = getattr(widget, "_Static__content", None)
    if content is not None:
        return str(content).lower()
    # Fallback: render to string
    return str(widget.render()).lower()


async def test_ready_workspace_opens_case_verdict(patched_app):
    """Launch with ready workspace -> CaseVerdictScreen."""
    from thesean.tui.screens.case_verdict import CaseVerdictScreen

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert isinstance(pilot.app.screen, CaseVerdictScreen)


async def test_draft_workspace_opens_case_verdict_idle(patched_empty_app):
    """Draft workspace with no results opens CaseVerdictScreen in idle mode."""
    from thesean.tui.screens.case_verdict import CaseVerdictScreen

    async with patched_empty_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert isinstance(pilot.app.screen, CaseVerdictScreen)


async def test_verdict_block_shows_regression(patched_app):
    """Verdict block should contain regression text when outcomes show regression."""
    from textual.widgets import Static

    from thesean.tui.screens.case_verdict import CaseVerdictScreen

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, CaseVerdictScreen)
        block = screen.query_one("#cv-verdict-block", Static)
        text = _static_text(block)
        assert "regression" in text or "underperformed" in text


async def test_episode_table_has_rows(patched_app):
    """Episode table should be populated with 2 rows matching episode_count."""
    from textual.widgets import DataTable

    from thesean.tui.screens.case_verdict import CaseVerdictScreen

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, CaseVerdictScreen)
        table = screen.query_one("#cv-episode-table", DataTable)
        assert table.row_count == 2


async def test_b_opens_builder_escape_returns(patched_app):
    """Press b to open RunBuilder, escape to return to CaseVerdict."""
    from thesean.tui.screens.case_verdict import CaseVerdictScreen
    from thesean.tui.screens.run_builder import RunBuilderScreen

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert isinstance(pilot.app.screen, CaseVerdictScreen)

        await pilot.press("b")
        await pilot.pause()
        assert isinstance(pilot.app.screen, RunBuilderScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(pilot.app.screen, CaseVerdictScreen)


async def test_enter_drills_into_investigation(patched_app):
    """Selecting an episode opens InvestigationScreen."""
    from thesean.tui.screens.case_verdict import CaseVerdictScreen
    from thesean.tui.screens.investigation import InvestigationScreen

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, CaseVerdictScreen)

        # Trigger episode selection directly (DataTable consumes enter in focused state)
        screen.action_select_episode()
        for _ in range(5):
            await pilot.pause()

        assert isinstance(pilot.app.screen, InvestigationScreen)


async def test_investigation_step_navigation(patched_app):
    """In investigation screen, step_forward/backward update TransportBar."""
    from thesean.tui.screens.case_verdict import CaseVerdictScreen
    from thesean.tui.screens.investigation import InvestigationScreen
    from thesean.tui.widgets.transport_bar import TransportBar

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, CaseVerdictScreen)

        # Navigate to investigation via action
        screen.action_select_episode()
        for _ in range(5):
            await pilot.pause()

        inv = pilot.app.screen
        assert isinstance(inv, InvestigationScreen)

        bar = inv.query_one(TransportBar)
        # Dummy adapter has no translator so max_step may be 0; set it explicitly
        bar.max_step = 10
        bar.current_step = 0
        await pilot.pause()

        bar.step_forward()
        await pilot.pause()
        assert bar.current_step == 1

        bar.step_backward()
        await pilot.pause()
        assert bar.current_step == 0


async def test_command_palette_opens_and_closes(patched_app):
    """Slash opens command palette, escape closes it."""
    from thesean.tui.screens.command_palette import CommandPaletteModal

    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        await pilot.press("slash")
        await pilot.pause()
        assert isinstance(pilot.app.screen, CommandPaletteModal)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(pilot.app.screen, CommandPaletteModal)


async def test_help_notification(patched_app):
    """Pressing ? posts a help notification."""
    async with patched_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        await pilot.press("question_mark")
        await pilot.pause()
        # Textual stores notifications; check at least one was posted
        assert len(pilot.app._notifications) > 0


async def test_draft_shows_idle_verdict(patched_empty_app):
    """Draft workspace verdict block shows no-results message."""
    from textual.widgets import Static

    from thesean.tui.screens.case_verdict import CaseVerdictScreen

    async with patched_empty_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, CaseVerdictScreen)
        block = screen.query_one("#cv-verdict-block", Static)
        text = _static_text(block)
        assert "no evaluation" in text or "no results" in text
