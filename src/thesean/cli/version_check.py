from __future__ import annotations

import threading


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _fetch_latest_version() -> str | None:
    """Return latest PyPI version string if newer than installed, else None."""
    try:
        import json
        import urllib.request

        from thesean import __version__

        resp = urllib.request.urlopen(
            "https://pypi.org/pypi/thesean/json", timeout=3
        )
        data = json.loads(resp.read())
        latest = data["info"]["version"]

        if _ver(latest) > _ver(__version__):
            return latest
    except Exception:
        pass
    return None


def check_for_update() -> None:
    """Print a notice if a newer version of thesean is available on PyPI."""

    def _check() -> None:
        latest = _fetch_latest_version()
        if latest:
            import typer

            from thesean import __version__

            typer.echo(
                f"\n  Thesean {latest} available (you have {__version__}). "
                f"Run: pip install --upgrade thesean\n"
            )

    threading.Thread(target=_check, daemon=True).start()
