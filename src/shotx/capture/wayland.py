"""Wayland capture backend.

Captures screens on Wayland compositors using a tiered strategy:

1. **Portal capture** (primary): Calls xdg-desktop-portal's Screenshot
   interface via D-Bus with interactive=false for instant capture.
   This is the standard, secure method that works on all Wayland
   compositors (GNOME, KDE, Sway, Hyprland, etc.).

2. **grim** (fallback): Subprocess call to grim for wlroots-based
   compositors where the portal may not be configured.

3. **Qt grabWindow** (last resort): Tries Qt6's built-in grab, which
   may work on some compositor/Qt combinations.

Monitor and window enumeration use compositor-specific D-Bus interfaces
where available (GNOME Shell Introspect, KDE's foreign-toplevel protocol).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtGui import QGuiApplication, QImage

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

    def capture_fullscreen(self, monitor_index: int | None = None, show_cursor: bool = False) -> QImage | None:
        """Capture the full screen on Wayland.

        Tries methods in order:
        1. xdg-desktop-portal Screenshot (D-Bus, interactive=false)
        2. grim subprocess (wlroots compositors)
        3. Qt6 grabWindow (last resort)
        """
        # Strategy 1: Portal (works on GNOME, KDE, most compositors)
        # GNOME/Portal natively handles cursor visibility interactively
        image = self._capture_via_portal()
        if image is not None:
            return image

        # Strategy 2: grim (wlroots: Sway, Hyprland, etc.)
        logger.info("Portal capture failed, trying grim")
        image = self._capture_via_grim(monitor_index, show_cursor)
        if image is not None:
            return image

        # Strategy 3: Qt grabWindow (last resort)
        logger.info("grim not available, trying Qt grabWindow")
        return self._capture_via_qt(monitor_index)

    def capture_active_window(self) -> QImage | None:
        """Capture the active window.

        On Wayland, direct window capture is restricted. For Phase 1,
        this falls back to fullscreen capture. Phase 2 will add proper
        window detection via our custom overlay.
        """
        logger.info("Active window capture falling back to fullscreen on Wayland")
        return self.capture_fullscreen()

    def get_monitors(self) -> list[MonitorInfo]:
        """Get monitor info from Qt6's screen list."""
        monitors = []
        primary = QGuiApplication.primaryScreen()

        for i, screen in enumerate(QGuiApplication.screens()):
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

        Tries compositor-specific D-Bus interfaces:
        - GNOME: org.gnome.Shell.Introspect
        - KDE/Sway: ext-foreign-toplevel-list (Phase 2)
        """
        windows = self._get_windows_gnome()
        if windows:
            return windows

        logger.debug("Window enumeration not available on this Wayland compositor")
        return []

    # --- Private capture methods ---

    def _capture_via_portal(self) -> QImage | None:
        """Capture screen using xdg-desktop-portal Screenshot D-Bus API.

        Uses low-level D-Bus message construction to avoid dbus_next's
        high-level proxy introspection, which fails on some portal
        property names containing hyphens (e.g., 'power-saver-enabled').

        How it works:
        1. Construct a Screenshot method call with interactive=true
        2. Send it on the session bus — compositor shows its native picker
        3. Listen for the Response signal with the screenshot URI
        4. Load the image from the file URI

        Note: GNOME denies interactive=false for non-privileged apps
        (response code 2). Using interactive=true shows the compositor's
        native screenshot dialog. In Phase 2, our custom overlay will
        capture the screen directly, bypassing the portal dialog.
        """
        try:
            from dbus_next import Message, MessageType, Variant
            from dbus_next.aio import MessageBus

            async def _take_screenshot() -> str | None:
                bus = await MessageBus().connect()
                unique_name = bus.unique_name

                # Build a predictable request token so we know which
                # object path the Response signal will arrive on.
                # The portal creates: /org/freedesktop/portal/desktop/request/{sender}/{token}
                token = "shotx_screenshot"
                sender_part = unique_name.lstrip(":").replace(".", "_") if unique_name else "sender"
                expected_request_path = (
                    f"/org/freedesktop/portal/desktop/request/{sender_part}/{token}"
                )

                # Set up signal listener BEFORE making the call
                response_future: asyncio.Future[str | None] = asyncio.get_event_loop().create_future()

                def on_message(msg: Message) -> None:
                    if response_future.done():
                        return
                    if (
                        msg.message_type == MessageType.SIGNAL
                        and msg.member == "Response"
                        and msg.path == expected_request_path
                    ):
                        # Signal body: (uint32 response, dict results)
                        response_code = msg.body[0]
                        results = msg.body[1]
                        if response_code == 0:
                            uri = results.get("uri")
                            if isinstance(uri, Variant):
                                uri = uri.value
                            response_future.set_result(str(uri) if uri else None)
                        else:
                            response_future.set_result(None)

                bus.add_message_handler(on_message)

                # Add match rule to receive the signal
                await bus.call(
                    Message(
                        destination="org.freedesktop.DBus",
                        path="/org/freedesktop/DBus",
                        interface="org.freedesktop.DBus",
                        member="AddMatch",
                        signature="s",
                        body=[
                            f"type='signal',interface='org.freedesktop.portal.Request',"
                            f"member='Response',path='{expected_request_path}'"
                        ],
                    )
                )

                # Construct the Screenshot method call manually
                # Signature: Screenshot(parent_window: s, options: a{sv})
                # interactive=True because GNOME denies non-interactive
                # screenshots from non-privileged apps
                options = {
                    "interactive": Variant("b", True),
                    "handle_token": Variant("s", token),
                }

                msg = await bus.call(
                    Message(
                        destination="org.freedesktop.portal.Desktop",
                        path="/org/freedesktop/portal/desktop",
                        interface="org.freedesktop.portal.Screenshot",
                        member="Screenshot",
                        signature="sa{sv}",
                        body=["", options],
                    )
                )

                if msg and msg.message_type == MessageType.METHOD_RETURN:
                    body = msg.body
                    if body and len(body) > 0 and isinstance(body[0], dict):
                        pass  # response = body[0] - unused but noted for future context if needed
                        # body[1] is result code (1=success)
                elif msg and msg.message_type == MessageType.ERROR:
                    logger.warning("Portal Screenshot call failed: %s", msg.body)
                    bus.disconnect()
                    return None

                # Wait for the Response signal
                try:
                    uri = await asyncio.wait_for(response_future, timeout=60.0)
                except asyncio.TimeoutError:
                    logger.warning("Portal screenshot timed out after 10s")
                    uri = None

                bus.remove_message_handler(on_message)
                bus.disconnect()
                return uri

            # Run async D-Bus call
            loop = asyncio.new_event_loop()
            try:
                uri = loop.run_until_complete(_take_screenshot())
            finally:
                loop.close()

            if uri is None:
                logger.warning("Portal returned no URI")
                return None

            # Convert file:// URI to local path
            parsed = urlparse(uri)
            file_path = Path(unquote(parsed.path))

            if not file_path.exists():
                logger.error("Portal screenshot file not found: %s", file_path)
                return None

            # Load as QImage
            image = QImage(str(file_path))
            if image.isNull():
                logger.error("Failed to load portal screenshot as QImage")
                return None

            logger.info(
                "Captured %dx%d image via xdg-desktop-portal",
                image.width(),
                image.height(),
            )

            # Clean up the temp file created by the portal
            with contextlib.suppress(OSError):
                file_path.unlink()

            return image

        except Exception as e:
            logger.warning("Portal capture failed: %s", e)
            return None

    def _capture_via_grim(self, monitor_index: int | None = None, show_cursor: bool = False) -> QImage | None:
        """Fallback capture using grim (for wlroots-based compositors).

        grim works with wlr-screencopy-unstable-v1 protocol
        (Sway, Hyprland, river, etc.).
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

            # Get screen name for specific monitor
            screen_name = None
            if monitor_index is not None:
                app = QGuiApplication.instance()
                if app:
                    screens = QGuiApplication.screens()
                    if 0 <= monitor_index < len(screens):
                        screen_name = screens[monitor_index].name()

            # Capture to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                cmd = ["grim"]
                if screen_name:
                    cmd.extend(["-o", screen_name])
                if show_cursor:
                    cmd.append("-c")
                cmd.append(tmp_path)

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode != 0:
                    logger.warning("grim failed: %s", result.stderr)
                    return None

                image = QImage(tmp_path)
                if image.isNull():
                    return None

                logger.info("Captured %dx%d image via grim", image.width(), image.height())
                return image

            finally:
                Path(tmp_path).unlink(missing_ok=True)

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.debug("grim unavailable: %s", e)
            return None

    def _capture_via_qt(self, monitor_index: int | None = None) -> QImage | None:
        """Last-resort capture using Qt6 grabWindow.

        This rarely works on Wayland (returns null on most compositors)
        but is kept as a fallback for edge cases.
        """
        app = QGuiApplication.instance()
        if app is None:
            return None

        screens = QGuiApplication.screens()
        if not screens:
            return None

        if monitor_index is not None and 0 <= monitor_index < len(screens):
            screen = screens[monitor_index]
        else:
            screen = QGuiApplication.primaryScreen()

        if screen is None:
            return None

        try:
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                logger.debug("Qt grabWindow returned null (expected on Wayland)")
                return None

            image = pixmap.toImage()
            if image.isNull():
                return None

            logger.info("Captured %dx%d via Qt grabWindow", image.width(), image.height())
            return image

        except Exception as e:
            logger.debug("Qt capture failed: %s", e)
            return None

    # --- Private window enumeration methods ---

    def _get_windows_gnome(self) -> list[WindowInfo]:
        """Get window list from GNOME Shell Introspect D-Bus interface.

        Available on GNOME desktops. Returns window geometry and metadata
        via org.gnome.Shell.Introspect.GetWindows().
        """
        try:
            import asyncio

            from dbus_next import Variant
            from dbus_next.aio import MessageBus

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
                # call_get_windows is added dynamically by dbus-next
                windows_data = await getattr(iface, "call_get_windows")()  # noqa: B009
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
