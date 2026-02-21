"""Clipboard operations for ShotX.

Copies captured images to the system clipboard. Uses a tiered approach:

1. Try subprocess clipboard tools (wl-copy, xclip, xsel) — these fork
   background processes that persist clipboard data after our process exits.
   No install required; uses whatever is already on the system.

2. Fall back to Qt's QClipboard — works when running as a long-lived tray
   app, but clipboard data is lost when one-shot CLI mode exits on Wayland.

Why subprocess tools? On Wayland, clipboard uses an ownership model — the
app that sets content must stay alive to serve paste requests. In one-shot
mode (shotx --capture-region), the process exits immediately. Tools like
wl-copy solve this by forking a daemon that serves the data.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication, QImage

logger = logging.getLogger(__name__)


def copy_image_to_clipboard(image: QImage) -> bool:
    """Copy a QImage to the system clipboard.

    Tries subprocess clipboard tools first (persistent across process exit),
    falls back to Qt clipboard.

    Args:
        image: The image to copy.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    if image.isNull():
        logger.error("Cannot copy null image to clipboard")
        return False

    # Try subprocess-based clipboard (persists after exit)
    if _copy_image_via_subprocess(image):
        return True

    # Fall back to Qt clipboard (works when app stays alive, e.g. tray mode)
    return _copy_image_via_qt(image)


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard.

    Args:
        text: The text to copy.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    app = QGuiApplication.instance()
    if app is None:
        logger.error("No QGuiApplication instance — cannot access clipboard")
        return False

    clipboard = app.clipboard()
    if clipboard is None:
        logger.error("Clipboard not available")
        return False

    try:
        clipboard.setText(text)
        logger.debug("Text copied to clipboard: %s", text[:80])
        return True
    except Exception as e:
        logger.error("Failed to copy text to clipboard: %s", e)
        return False


# --- Private implementation ---


def _image_to_png_bytes(image: QImage) -> bytes | None:
    """Convert a QImage to PNG bytes in memory."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        logger.error("Failed to encode image as PNG for clipboard")
        return None
    return bytes(buffer.data())


def _copy_image_via_subprocess(image: QImage) -> bool:
    """Try to copy image via subprocess clipboard tools.

    Attempts tools in order: wl-copy (Wayland), xclip (X11), xsel (X11).
    These tools fork daemon processes that keep serving the clipboard
    data after our process exits — solving the Wayland ownership issue.

    Returns True if successful, False if no tool is available.
    """
    png_data = _image_to_png_bytes(image)
    if png_data is None:
        return False

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()

    # On Wayland, try wl-copy first
    if session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        if _try_clipboard_cmd(["wl-copy", "--type", "image/png"], png_data):
            return True

    # On X11 (or as fallback), try xclip then xsel
    if _try_clipboard_cmd(
        ["xclip", "-selection", "clipboard", "-target", "image/png", "-i"],
        png_data,
    ):
        return True

    if _try_clipboard_cmd(
        ["xsel", "--clipboard", "--input"],
        png_data,
    ):
        return True

    logger.debug(
        "No subprocess clipboard tool found (wl-copy, xclip, xsel). "
        "Falling back to Qt clipboard."
    )
    return False


def _try_clipboard_cmd(cmd: list[str], data: bytes) -> bool:
    """Try running a clipboard command, piping data to stdin.

    Uses Popen instead of subprocess.run because tools like xclip
    stay alive to serve paste requests. We write data to stdin,
    close it, and let the tool run in the background.

    Returns True if data was written successfully, False otherwise.
    Silently returns False if the command is not installed.
    """
    tool = cmd[0]
    if shutil.which(tool) is None:
        return False

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Write PNG data and close stdin — the tool reads it all,
        # then serves the clipboard data in the background
        proc.stdin.write(data)
        proc.stdin.close()

        # Give it a moment to read the data and start serving
        try:
            proc.wait(timeout=2)
            # If it exited quickly, check the return code
            if proc.returncode != 0:
                logger.debug("%s failed (exit %d)", tool, proc.returncode)
                return False
        except subprocess.TimeoutExpired:
            # Expected for xclip — it stays alive to serve paste requests.
            # That's exactly what we want.
            pass

        logger.debug("Image copied to clipboard via %s", tool)
        return True
    except (FileNotFoundError, OSError) as e:
        logger.debug("%s error: %s", tool, e)
        return False


def _copy_image_via_qt(image: QImage) -> bool:
    """Copy image via Qt's QClipboard.

    Works reliably when the app stays alive (tray mode). In one-shot
    mode on Wayland, the clipboard data may be lost when the process exits.
    """
    app = QGuiApplication.instance()
    if app is None:
        logger.error("No QGuiApplication instance — cannot access clipboard")
        return False

    clipboard = app.clipboard()
    if clipboard is None:
        logger.error("Clipboard not available")
        return False

    try:
        clipboard.setImage(image)
        logger.debug("Image copied to clipboard via Qt (%dx%d)", image.width(), image.height())
        return True
    except Exception as e:
        logger.error("Failed to copy image to clipboard: %s", e)
        return False
