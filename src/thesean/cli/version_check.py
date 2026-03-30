from __future__ import annotations

import threading


def check_for_update() -> None:
    """Print a notice if a newer version of thesean is available on PyPI."""

    def _check() -> None:
        try:
            import json
            import urllib.request

            from thesean import __version__

            resp = urllib.request.urlopen(
                "https://pypi.org/pypi/thesean/json", timeout=3
            )
            data = json.loads(resp.read())
            latest = data["info"]["version"]

            if latest != __version__:
                import typer

                typer.echo(
                    f"\n  TheSean {latest} available (you have {__version__}). "
                    f"Run: pip install --upgrade thesean\n"
                )
        except Exception:
            pass  # network down, PyPI unreachable, not published yet — all fine

    threading.Thread(target=_check, daemon=True).start()
