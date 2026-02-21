"""Tests for session detection and backend availability.

These test the decision logic that determines which capture backend
gets used. All tests mock environment variables — no display server needed.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from shotx.capture.factory import detect_session_type
from shotx.capture.wayland import WaylandCaptureBackend
from shotx.capture.x11 import X11CaptureBackend


class TestDetectSessionType:
    """Tests for detect_session_type() — the Wayland vs X11 decision point."""

    def test_wayland_via_xdg_session_type(self) -> None:
        """XDG_SESSION_TYPE=wayland should be detected as wayland."""
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "wayland"

    def test_x11_via_xdg_session_type(self) -> None:
        """XDG_SESSION_TYPE=x11 should be detected as x11."""
        env = {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "x11"

    def test_wayland_fallback_via_wayland_display(self) -> None:
        """WAYLAND_DISPLAY set (no XDG_SESSION_TYPE) should detect wayland."""
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "wayland"

    def test_x11_fallback_via_display(self) -> None:
        """DISPLAY set (no XDG_SESSION_TYPE, no WAYLAND_DISPLAY) should detect x11."""
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "", "DISPLAY": ":0"}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "x11"

    def test_unknown_when_no_env_vars(self) -> None:
        """No relevant env vars should return 'unknown'."""
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "unknown"

    def test_xdg_session_type_takes_priority(self) -> None:
        """XDG_SESSION_TYPE should take priority over WAYLAND_DISPLAY and DISPLAY."""
        # Scenario: XWayland — XDG says x11 but WAYLAND_DISPLAY is also set
        env = {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "x11"

    def test_case_insensitive(self) -> None:
        """Session type detection should be case-insensitive."""
        env = {"XDG_SESSION_TYPE": "Wayland", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "wayland"

    def test_whitespace_trimmed(self) -> None:
        """Whitespace in env var should be trimmed."""
        env = {"XDG_SESSION_TYPE": "  x11  ", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_session_type() == "x11"


class TestWaylandBackendAvailability:
    """Tests for WaylandCaptureBackend.is_available()."""

    def test_available_via_xdg_session_type(self) -> None:
        """Wayland backend should be available when XDG_SESSION_TYPE=wayland."""
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert WaylandCaptureBackend().is_available() is True

    def test_available_via_wayland_display(self) -> None:
        """Wayland backend should be available when WAYLAND_DISPLAY is set."""
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "wayland-0"}
        with patch.dict(os.environ, env, clear=False):
            assert WaylandCaptureBackend().is_available() is True

    def test_not_available_on_x11(self) -> None:
        """Wayland backend should NOT be available on a pure X11 session."""
        env = {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert WaylandCaptureBackend().is_available() is False


class TestX11BackendAvailability:
    """Tests for X11CaptureBackend.is_available()."""

    def test_available_when_display_set(self) -> None:
        """X11 backend should be available when DISPLAY is set."""
        env = {"DISPLAY": ":0"}
        with patch.dict(os.environ, env, clear=False):
            assert X11CaptureBackend().is_available() is True

    def test_not_available_without_display(self) -> None:
        """X11 backend should NOT be available without DISPLAY."""
        env = {"DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert X11CaptureBackend().is_available() is False

    def test_available_on_xwayland(self) -> None:
        """X11 backend should be available on XWayland (DISPLAY is set)."""
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
        with patch.dict(os.environ, env, clear=False):
            # DISPLAY is set, so X11 backend CAN work (via XWayland)
            assert X11CaptureBackend().is_available() is True


class TestBackendProperties:
    """Test that backend metadata is correct."""

    def test_wayland_backend_name(self) -> None:
        assert WaylandCaptureBackend().name == "Wayland"

    def test_x11_backend_name(self) -> None:
        assert X11CaptureBackend().name == "X11"
