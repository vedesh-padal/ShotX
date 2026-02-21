"""X11 capture backend.

Captures screens on X11 display servers using Qt6's built-in X11 support.
Window enumeration uses subprocess calls to standard X11 tools (wmctrl, xdotool)
or falls back to Qt's window list.

This backend works on X11 sessions and as a fallback on XWayland.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess

from PySide6.QtGui import QGuiApplication, QImage

from shotx.capture.backend import CaptureBackend, MonitorInfo, WindowInfo

logger = logging.getLogger(__name__)


class X11CaptureBackend(CaptureBackend):
    """Capture backend for X11 display servers."""

    @property
    def name(self) -> str:
        return "X11"

    def is_available(self) -> bool:
        """Check if X11 display is available."""
        return bool(os.environ.get("DISPLAY"))

    def capture_fullscreen(self, monitor_index: int | None = None) -> QImage | None:
        """Capture the full screen using Qt6's grabWindow on X11.

        On X11, grabWindow(0) captures the root window which contains
        all visible content across all monitors.
        """
        app = QGuiApplication.instance()
        if app is None:
            logger.error("No QGuiApplication instance")
            return None

        screens = app.screens()
        if not screens:
            logger.error("No screens found")
            return None

        if monitor_index is not None:
            # Capture a specific monitor by grabbing its region from root
            if 0 <= monitor_index < len(screens):
                screen = screens[monitor_index]
            else:
                logger.error(
                    "Monitor index %d out of range (have %d monitors)",
                    monitor_index,
                    len(screens),
                )
                return None
        else:
            screen = app.primaryScreen()

        if screen is None:
            logger.error("No primary screen available")
            return None

        try:
            # grabWindow(0) captures the root window (entire X11 display)
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                logger.warning("grabWindow returned null pixmap")
                return None

            image = pixmap.toImage()
            if image.isNull():
                logger.warning("pixmap.toImage() returned null image")
                return None

            logger.debug(
                "Captured %dx%d image from X11 screen '%s'",
                image.width(),
                image.height(),
                screen.name(),
            )
            return image

        except Exception as e:
            logger.error("X11 capture failed: %s", e)
            return None

    def capture_active_window(self) -> QImage | None:
        """Capture the currently focused window.

        Uses xdotool to get the active window ID, then grabs just that window.
        Falls back to fullscreen if xdotool is unavailable.
        """
        window_id = self._get_active_window_id()
        if window_id is None:
            logger.info("Could not get active window, falling back to fullscreen")
            return self.capture_fullscreen()

        app = QGuiApplication.instance()
        if app is None:
            return None

        screen = app.primaryScreen()
        if screen is None:
            return None

        try:
            pixmap = screen.grabWindow(window_id)
            if pixmap.isNull():
                logger.warning("grabWindow(%d) returned null pixmap", window_id)
                return self.capture_fullscreen()

            image = pixmap.toImage()
            if image.isNull():
                return self.capture_fullscreen()

            logger.debug(
                "Captured window %d: %dx%d",
                window_id,
                image.width(),
                image.height(),
            )
            return image

        except Exception as e:
            logger.error("Window capture failed: %s", e)
            return self.capture_fullscreen()

    def get_monitors(self) -> list[MonitorInfo]:
        """Get monitor info from Qt6's screen list."""
        app = QGuiApplication.instance()
        if app is None:
            return []

        monitors = []
        primary = app.primaryScreen()

        for i, screen in enumerate(app.screens()):
            geo = screen.geometry()
            monitors.append(
                MonitorInfo(
                    name=screen.name() or f"Monitor {i}",
                    x=geo.x(),
                    y=geo.y(),
                    width=geo.width(),
                    height=geo.height(),
                    scale_factor=screen.devicePixelRatio(),
                    is_primary=(screen == primary),
                )
            )

        return monitors

    def get_windows(self) -> list[WindowInfo]:
        """Get visible window list using wmctrl.

        wmctrl provides window geometry, title, and desktop information
        via the _NET_CLIENT_LIST EWMH protocol.
        """
        return self._get_windows_wmctrl()

    # --- Private methods ---

    def _get_active_window_id(self) -> int | None:
        """Get the active window ID using xdotool."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired) as e:
            logger.debug("xdotool not available: %s", e)
        return None

    def _get_windows_wmctrl(self) -> list[WindowInfo]:
        """Get window list using wmctrl -lG.

        Output format: <WID> <DESKTOP> <X> <Y> <W> <H> <HOSTNAME> <TITLE>
        """
        try:
            result = subprocess.run(
                ["wmctrl", "-lG"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.debug("wmctrl failed: %s", result.stderr)
                return []

            active_wid = self._get_active_window_id()
            windows = []

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                # Parse: 0x04c00003  0  0    27   1920 1027  hostname Title text here
                parts = line.split(None, 7)
                if len(parts) < 8:
                    continue

                try:
                    wid = int(parts[0], 16)  # Window IDs are hex
                    x = int(parts[2])
                    y = int(parts[3])
                    w = int(parts[4])
                    h = int(parts[5])
                    # parts[6] is hostname, parts[7] is title
                    title = parts[7] if len(parts) > 7 else ""

                    # Get app name from window class (WM_CLASS)
                    app_name = self._get_window_class(wid) or ""

                    windows.append(
                        WindowInfo(
                            window_id=wid,
                            title=title,
                            app_name=app_name,
                            x=x,
                            y=y,
                            width=w,
                            height=h,
                            is_active=(wid == active_wid),
                        )
                    )
                except (ValueError, IndexError) as e:
                    logger.debug("Skipping window line: %s (%s)", line, e)
                    continue

            return windows

        except FileNotFoundError:
            logger.debug("wmctrl not installed")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("wmctrl timed out")
            return []

    def _get_window_class(self, window_id: int) -> str | None:
        """Get WM_CLASS for a window using xprop."""
        try:
            result = subprocess.run(
                ["xprop", "-id", str(window_id), "WM_CLASS"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Output: WM_CLASS(STRING) = "instance", "class"
                match = re.search(r'"([^"]+)"(?:,\s*"([^"]+)")?', result.stdout)
                if match:
                    return match.group(2) or match.group(1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
