"""Wayland capture backend.

Captures screens on Wayland compositors using two strategies:

1. **Instant capture** (primary): Uses Qt6's QScreen.grabWindow() which
   internally uses the xdg-desktop-portal with interactive=false.
   No dialog appears — the screenshot is taken instantly.

2. **Portal capture** (fallback): Calls xdg-desktop-portal's Screenshot
   interface via D-Bus. This may show a compositor dialog depending on
   the compositor's implementation.

Monitor and window enumeration use compositor-specific D-Bus interfaces
where available (GNOME Shell Introspect, KDE's foreign-toplevel protocol).
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage, QScreen

from shotx.capture.backend import CaptureBackend, MonitorInfo, WindowInfo

logger = logging.getLogger(__name__)


class WaylandCaptureBackend(CaptureBackend):
    """Capture backend for Wayland display servers."""

    @property
    def name(self) -> str:
        return "Wayland"

    def is_available(self) -> bool:
        """Check if we're running on a Wayland session."""
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
        return session_type == "wayland" or bool(wayland_display)

    def capture_fullscreen(self, monitor_index: int | None = None) -> QImage | None:
        """Capture the full screen using Qt6.

        Qt6 on Wayland uses the portal internally with interactive=false,
        so this captures instantly without showing any dialog.
        """
        app = QGuiApplication.instance()
        if app is None:
            logger.error("No QGuiApplication instance. Cannot capture on Wayland.")
            return None

        screens = app.screens()
        if not screens:
            logger.error("No screens found")
            return None

        if monitor_index is not None:
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

        # Try Qt6's built-in grab first
        image = self._capture_via_qt(screen)
        if image is not None:
            return image

        # Fallback: try grim (wlroots compositors)
        logger.info("Qt capture returned empty, trying grim fallback")
        return self._capture_via_grim(screen)

    def capture_active_window(self) -> QImage | None:
        """Capture the active window.

        On Wayland, direct window capture is restricted. We use the
        xdg-desktop-portal Screenshot interface which allows the
        compositor to handle window selection.

        For Phase 1, this falls back to fullscreen capture.
        In Phase 2, our custom overlay will handle window selection.
        """
        # For now, delegate to fullscreen capture.
        # Phase 2 will add proper window detection and cropping.
        logger.info("Active window capture falling back to fullscreen on Wayland")
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
        """Get window list from compositor.

        On Wayland, window enumeration is restricted by design.
        We try compositor-specific D-Bus interfaces:
        - GNOME: org.gnome.Shell.Introspect
        - KDE/Sway: ext-foreign-toplevel-list (not yet implemented)

        Returns empty list if unavailable. Phase 2 will expand this
        with edge-detection fallback for auto-region detection.
        """
        # Try GNOME Shell Introspect
        windows = self._get_windows_gnome()
        if windows:
            return windows

        # Other compositor support will be added in Phase 2
        logger.debug("Window enumeration not available on this Wayland compositor")
        return []

    # --- Private capture methods ---

    def _capture_via_qt(self, screen: QScreen) -> QImage | None:
        """Capture screen using Qt6's grabWindow.

        On Wayland, Qt6 internally uses the xdg-desktop-portal
        with interactive=false for instant capture.
        """
        try:
            # grabWindow(0) captures the entire screen
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                logger.warning("Qt grabWindow returned null pixmap")
                return None

            image = pixmap.toImage()
            if image.isNull():
                logger.warning("Qt pixmap.toImage() returned null image")
                return None

            logger.debug(
                "Captured %dx%d image via Qt from screen '%s'",
                image.width(),
                image.height(),
                screen.name(),
            )
            return image

        except Exception as e:
            logger.error("Qt capture failed: %s", e)
            return None

    def _capture_via_grim(self, screen: QScreen) -> QImage | None:
        """Fallback capture using grim (for wlroots-based compositors).

        grim is a simple screenshot tool for Wayland that works with
        wlr-screencopy-unstable-v1 protocol (used by Sway, Hyprland, etc.).
        """
        try:
            # Check if grim is available
            result = subprocess.run(
                ["which", "grim"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.debug("grim not found in PATH")
                return None

            # Capture to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                cmd = ["grim"]
                # If specific output, add -o flag
                if screen.name():
                    cmd.extend(["-o", screen.name()])
                cmd.append(tmp_path)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode != 0:
                    logger.warning("grim capture failed: %s", result.stderr)
                    return None

                image = QImage(tmp_path)
                if image.isNull():
                    logger.warning("Failed to load grim output as QImage")
                    return None

                logger.debug("Captured %dx%d image via grim", image.width(), image.height())
                return image

            finally:
                # Clean up temp file
                Path(tmp_path).unlink(missing_ok=True)

        except FileNotFoundError:
            logger.debug("grim not installed")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("grim capture timed out")
            return None
        except Exception as e:
            logger.error("grim capture failed: %s", e)
            return None

    # --- Private window enumeration methods ---

    def _get_windows_gnome(self) -> list[WindowInfo]:
        """Get window list from GNOME Shell Introspect D-Bus interface.

        Available on GNOME desktops. Returns window geometry and metadata
        via org.gnome.Shell.Introspect.GetWindows().
        """
        try:
            import asyncio
            from dbus_next.aio import MessageBus
            from dbus_next import Variant

            async def _fetch() -> list[WindowInfo]:
                bus = await MessageBus().connect()
                introspection = await bus.introspect(
                    "org.gnome.Shell.Introspect",
                    "/org/gnome/Shell/Introspect",
                )
                proxy = bus.get_proxy_object(
                    "org.gnome.Shell.Introspect",
                    "/org/gnome/Shell/Introspect",
                    introspection,
                )
                iface = proxy.get_interface("org.gnome.Shell.Introspect")
                windows_data = await iface.call_get_windows()
                bus.disconnect()

                windows = []
                for wid_str, props in windows_data.items():
                    try:
                        wid = int(wid_str)

                        # Extract properties — they come as Variant objects
                        def get_val(d: dict, key: str, default: object = "") -> object:
                            v = d.get(key)
                            return v.value if isinstance(v, Variant) else (v or default)

                        title = str(get_val(props, "title", ""))
                        app_id = str(get_val(props, "app-id", ""))
                        rect = get_val(props, "outer-rect")
                        is_focus = bool(get_val(props, "has-focus", False))

                        if rect and hasattr(rect, "value"):
                            rect = rect.value

                        x, y, w, h = 0, 0, 0, 0
                        if isinstance(rect, (list, tuple)) and len(rect) >= 4:
                            x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])

                        windows.append(
                            WindowInfo(
                                window_id=wid,
                                title=title,
                                app_name=app_id,
                                x=x,
                                y=y,
                                width=w,
                                height=h,
                                is_active=is_focus,
                            )
                        )
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.debug("Skipping window %s: %s", wid_str, e)
                        continue

                return windows

            # Run async code in a new event loop
            # (we can't assume the Qt event loop is running at this point)
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_fetch())
            finally:
                loop.close()

        except Exception as e:
            logger.debug("GNOME Shell Introspect not available: %s", e)
            return []
