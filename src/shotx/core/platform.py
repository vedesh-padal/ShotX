"""Platform detection utilities.

Centralises all Wayland / X11 / display-server detection into one place.
Previously this logic was duplicated across factory.py, wayland.py,
recorder.py, clipboard.py, and hotkey_settings_page.py.
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def session_type() -> str:
    """Detect the current display session type.

    Checks ``XDG_SESSION_TYPE`` first (set by the login manager on all
    modern Linux distros), then falls back to display-specific env vars.

    Returns:
        ``'wayland'``, ``'x11'``, or ``'unknown'``.
    """
    st = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()
    if st in ("wayland", "x11"):
        return st

    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"

    return "unknown"


def is_wayland() -> bool:
    """Return ``True`` if the current session is Wayland."""
    return session_type() == "wayland"


def is_x11() -> bool:
    """Return ``True`` if the current session is X11."""
    return session_type() == "x11"
