"""Capture backend factory.

Auto-detects the active display server (Wayland or X11) and returns
the appropriate capture backend. Falls back gracefully if one is unavailable.
"""

from __future__ import annotations

import os
import logging

from shotx.capture.backend import CaptureBackend

logger = logging.getLogger(__name__)


def detect_session_type() -> str:
    """Detect the current display session type.

    Checks XDG_SESSION_TYPE environment variable, which is set by
    the login manager (GDM, SDDM, etc.) on all modern Linux distros.

    Returns:
        'wayland', 'x11', or 'unknown'
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()
    if session_type in ("wayland", "x11"):
        return session_type

    # Fallback: check for Wayland-specific env vars
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"

    # Fallback: check for X11-specific env vars
    if os.environ.get("DISPLAY"):
        return "x11"

    return "unknown"


def create_capture_backend(force_backend: str | None = None) -> CaptureBackend:
    """Create and return the appropriate capture backend.

    Args:
        force_backend: If set, force a specific backend ('wayland' or 'x11').
                       Useful for testing or overriding auto-detection.

    Returns:
        An instance of CaptureBackend for the current display server.

    Raises:
        RuntimeError: If no suitable backend is available.
    """
    session_type = force_backend or detect_session_type()
    logger.info("Detected session type: %s", session_type)

    if session_type == "wayland":
        try:
            from shotx.capture.wayland import WaylandCaptureBackend

            backend = WaylandCaptureBackend()
            if backend.is_available():
                logger.info("Using Wayland capture backend")
                return backend
            logger.warning("Wayland backend not available, falling back to X11")
        except ImportError:
            logger.warning("Wayland backend import failed, falling back to X11")

    if session_type in ("x11", "wayland"):
        # Try X11 as primary (if x11 session) or fallback (if wayland failed)
        try:
            from shotx.capture.x11 import X11CaptureBackend

            backend = X11CaptureBackend()
            if backend.is_available():
                logger.info("Using X11 capture backend")
                return backend
            logger.warning("X11 backend not available")
        except ImportError:
            logger.warning("X11 backend import failed")

    raise RuntimeError(
        f"No capture backend available for session type '{session_type}'. "
        "ShotX requires either a Wayland or X11 display server. "
        "Please ensure you are running a graphical desktop session."
    )
