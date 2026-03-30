from __future__ import annotations

import typer

app = typer.Typer(name="thesean", help="Regression thesean harness for ML pipelines.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Launch TUI when no subcommand is given."""
    from thesean.cli.version_check import check_for_update

    check_for_update()

    if ctx.invoked_subcommand is None:
        from thesean.tui.app import TheSeanApp

        try:
            TheSeanApp().run()
        except (KeyboardInterrupt, SystemExit):
            pass
