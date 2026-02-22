"""Desktop notifications for ShotX.

Shows notifications after capture with actions to open the file
or its containing folder.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from PySide6.QtWidgets import QSystemTrayIcon

logger = logging.getLogger(__name__)


def notify_capture_success(
    tray_icon: QSystemTrayIcon | None,
    file_path: Path | None,
    message: str | None = None,
) -> None:
    """Show a notification that a screenshot was captured.

    Args:
        tray_icon: System tray icon for showing notifications.
        file_path: Path to the saved screenshot (may be None if only clipboard).
        message: Custom message override.
    """
    if tray_icon is None:
        logger.debug("No tray icon, skipping notification")
        return

    if message is None:
        if file_path:
            message = f"Saved to {file_path.name}"
        else:
            message = "Copied to clipboard"

    # Try interactive native notification if we have a file path
    if file_path:
        def _interactive_worker() -> None:
            try:
                result = subprocess.run(
                    [
                        "notify-send",
                        "-a", "ShotX",
                        "-i", "camera-photo",
                        "ShotX — Capture",
                        message,
                        "--action=open=View Image",
                        "--action=folder=Show in Folder",
                        "-t", "5000",
                    ],
                    capture_output=True,
                    text=True,
                )
                action = result.stdout.strip()
                if action == "open":
                    open_file(file_path)
                elif action == "folder":
                    open_folder(file_path)
            except (FileNotFoundError, Exception) as e:
                logger.debug("notify-send with actions failed: %s", e)
                # Fallback to Qt notification without actions
                tray_icon.showMessage(
                    "ShotX — Screenshot captured",
                    message,
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
                
        threading.Thread(target=_interactive_worker, daemon=True).start()
    else:
        # Standard Qt notification for clipboard-only
        tray_icon.showMessage(
            "ShotX — Screenshot captured",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    logger.debug("Notification shown: %s", message)


def notify_error(
    tray_icon: QSystemTrayIcon | None,
    message: str,
) -> None:
    """Show an error notification."""
    if tray_icon is None:
        logger.error("Notification (no tray): %s", message)
        return

    tray_icon.showMessage(
        "ShotX — Error",
        message,
        QSystemTrayIcon.MessageIcon.Critical,
        5000,  # 5 seconds
    )

    logger.error("Error notification: %s", message)


def notify_info(
    tray_icon: QSystemTrayIcon | None,
    title: str,
    message: str,
) -> None:
    """Show an informational notification."""
    if tray_icon is None:
        logger.info("Notification (no tray): %s - %s", title, message)
        return

    tray_icon.showMessage(
        title,
        message,
        QSystemTrayIcon.MessageIcon.Information,
        5000,  # 5 seconds
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
