"""Desktop notifications for ShotX.

Shows notifications after capture with actions to open the file
or its containing folder.
"""

from __future__ import annotations

import logging
import logging
import threading
from pathlib import Path

from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtCore import QTimer

# Import PyGObject for native DBus notifications
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

# Raw DBus connection (safe to mix with Qt, unlike Gio.Application)
_dbus_conn = None
_notification_paths: dict[int, str] = {}

def init_notifications():
    """Initialize DBus connection and signal listener on the main thread."""
    global _dbus_conn
    
    if _dbus_conn is not None:
        return
        
    try:
        # Get the session bus
        _dbus_conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        
        # Subscribe to notification clicks
        _dbus_conn.signal_subscribe(
            "org.freedesktop.Notifications",
            "org.freedesktop.Notifications",
            "ActionInvoked",
            "/org/freedesktop/Notifications",
            None,
            Gio.DBusSignalFlags.NONE,
            _on_action_invoked,
            None
        )
        logger.debug("Raw DBus notification listener initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize raw DBus connection: {e}")

def _on_action_invoked(conn, sender, obj_path, iface, signal, params, user_data):
    """Callback when ANY notification action is clicked on the system."""
    try:
        notif_id, action_name = params.unpack()
        
        if notif_id in _notification_paths and action_name == "default":
            file_path_str = _notification_paths[notif_id]
            logger.debug(f"Action clicked for notification ID {notif_id}, opening {file_path_str}")
            import subprocess
            subprocess.run(["xdg-open", file_path_str], check=True)
            
            # Optionally clean up the dictionary
            del _notification_paths[notif_id]
    except Exception as e:
        logger.error(f"Error handling DBus action click: {e}")

def _send_dbus_notification(title: str, body: str, icon: str, urgency: int = 1, file_path: str = None) -> None:
    """Helper to send a raw DBus message."""
    global _dbus_conn
    if _dbus_conn is None:
        init_notifications()
        
    if _dbus_conn is None:
        raise Exception("DBus connection not available.")

    actions = ["default", "Open"] if file_path else []
    
    # Send the raw Notification DBus call
    res = _dbus_conn.call_sync(
        "org.freedesktop.Notifications",         # bus_name
        "/org/freedesktop/Notifications",        # object_path
        "org.freedesktop.Notifications",         # interface_name
        "Notify",                                # method_name
        GLib.Variant("(susssasa{sv}i)", (
            "ShotX",                             # app_name
            0,                                   # replaces_id
            icon,                                # app_icon
            title,                               # summary
            body,                                # body
            actions,                             # actions
            {"urgency": GLib.Variant("y", urgency)},  # hints (0=low, 1=normal, 2=critical)
            5000 if urgency < 2 else 10000       # expire_timeout
        )),
        None,                                    # reply_type
        Gio.DBusCallFlags.NONE,
        -1,
        None
    )
    
    notif_id = res.unpack()[0]
    
    if file_path:
        _notification_paths[notif_id] = file_path


def notify_capture_success(
    tray_icon: QSystemTrayIcon | None,
    file_path: Path | None,
    message: str | None = None,
) -> None:
    """Show a native DBus interactive notification on Linux.

    Args:
        tray_icon: Fallback sys tray for older DEs.
        file_path: Path to the saved screenshot.
        message: Custom message override.
    """
    if message is None:
        if file_path:
            message = f"Saved to:\n{file_path}"
        else:
            message = "Copied to clipboard"

    try:
        # Urgency 2 = Critical (Needed on GNOME to bypass focus-stealing prevention)
        _send_dbus_notification(
            title="ShotX \u2014 Screenshot captured",
            body=message,
            icon="camera-photo",
            urgency=2,
            file_path=str(file_path) if file_path else None
        )
        logger.debug("Native raw DBus notification shown for capture.")
    except Exception as e:
        logger.warning(f"Native Gio notifications failed, falling back to Qt: {e}")
        if tray_icon:
            QTimer.singleShot(0, lambda: tray_icon.showMessage(
                "ShotX \u2014 Screenshot captured",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            ))

    logger.debug("Notification task completed: %s", message)


def notify_error(
    tray_icon: QSystemTrayIcon | None,
    message: str,
    file_path: Path | None = None,
) -> None:
    """Show an error notification.

    Args:
        tray_icon: Fallback sys tray for older DEs.
        message: The error message.
        file_path: Optional path to make the notification clickable.
    """
    logger.error("Error notification: %s", message)

    try:
        # Urgency 2 = Critical
        _send_dbus_notification(
            title="ShotX \u2014 Error",
            body=message,
            icon="dialog-error",
            urgency=2,
            file_path=str(file_path) if file_path else None
        )
        logger.debug("Native raw DBus error notification shown.")
    except Exception as e:
        logger.warning(f"Native Gio notifications failed, falling back to Qt: {e}")
        if tray_icon:
            # We don't use singleShot here because errors might be called from main thread
            tray_icon.showMessage(
                "ShotX \u2014 Error",
                message,
                QSystemTrayIcon.MessageIcon.Critical,
                5000,  # 5 seconds
            )


def notify_info(
    tray_icon: QSystemTrayIcon | None,
    title: str,
    message: str,
) -> None:
    """Show a general info notification.

    Args:
        tray_icon: Fallback sys tray for older DEs.
        title: Notification title.
        message: The info message.
    """
    try:
        # Urgency 2 = Critical
        _send_dbus_notification(
            title=title,
            body=message,
            icon="dialog-information",
            urgency=2,
            file_path=None
        )
        logger.debug("Native raw DBus info notification shown.")
    except Exception as e:
        logger.warning(f"Native Gio notifications failed, falling back to Qt: {e}")
        if tray_icon:
            tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
    logger.info("Info notification %s: %s", title, message)


def open_file(file_path: Path) -> bool:
    """Open a file with the default application.

    Uses xdg-open which works on all Linux desktop environments.
    """
    try:
        subprocess.Popen(
            ["xdg-open", str(file_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        logger.error("xdg-open not found — cannot open file")
        return False


def open_folder(file_path: Path) -> bool:
    """Open the containing folder in the file manager.

    Shows the folder that contains the given file.
    """
    folder = file_path.parent if file_path.is_file() else file_path
    try:
        subprocess.Popen(
            ["xdg-open", str(folder)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        logger.error("xdg-open not found — cannot open folder")
        return False
