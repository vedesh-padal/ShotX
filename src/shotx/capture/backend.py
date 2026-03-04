"""Abstract capture backend interface.

This module defines the contract that all capture backends (Wayland, X11,
potentially macOS) must implement. The abstraction allows the rest of ShotX
to be display-server-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorInfo:
    """Information about a connected display monitor."""

    name: str
    x: int
    y: int
    width: int
    height: int
    scale_factor: float = 1.0
    is_primary: bool = False


@dataclass(frozen=True)
class WindowInfo:
    """Information about a visible window.

    Used for auto-detect region highlighting in Phase 2.
    """

    window_id: int
    title: str
    app_name: str
    x: int
    y: int
    width: int
    height: int
    is_active: bool = False


class CaptureBackend(ABC):
    """Abstract base class for screen capture backends.

    Each display server (Wayland, X11) provides its own implementation.
    The backend handles the platform-specific mechanics of grabbing pixels,
    while the rest of ShotX works with QImage objects.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this backend (e.g., 'Wayland', 'X11')."""
        ...

    @abstractmethod
    def capture_fullscreen(self, monitor_index: int | None = None, show_cursor: bool = False) -> "QImage | None":
        """Capture the entire screen.

        Args:
            monitor_index: If specified, capture only this monitor.
                           If None, capture the primary monitor.
            show_cursor: Whether to include the mouse cursor in the capture.

        Returns:
            QImage of the captured screen, or None if capture failed.
        """
        ...

    @abstractmethod
    def capture_active_window(self) -> "QImage | None":
        """Capture the currently focused window.

        Returns:
            QImage of the active window, or None if capture failed.
        """
        ...

    @abstractmethod
    def get_monitors(self) -> list[MonitorInfo]:
        """Return a list of connected monitors with geometry.

        Used for multi-monitor support and monitor-specific capture.
        """
        ...

    @abstractmethod
    def get_windows(self) -> list[WindowInfo]:
        """Return a list of visible windows with geometry.

        Used in Phase 2 for auto-detect region highlighting.
        Returns an empty list if window enumeration is not supported
        (e.g., on Wayland without the foreign-toplevel protocol).
        """
        ...

    def is_available(self) -> bool:
        """Check if this backend can function in the current environment.

        Override this to perform environment checks (e.g., is Wayland
        session active? Is xdg-desktop-portal running?).

        Returns True by default — subclasses should override with real checks.
        """
        return True
