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

import logging
import os
import shutil
import subprocess
from typing import cast

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
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

    success = False

    # Try Qt clipboard (ground truth for the app, helpful in tray mode)
    if _copy_image_via_qt(image):
        success = True

    # Also try subprocess-based clipboard (persists after exit, essential for one-shot)
    if _copy_image_via_subprocess(image):
        success = True

    return success


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard.

    Args:
        text: The text to copy.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    if not text:
        logger.error("Cannot copy empty text to clipboard")
        return False

    success = False

    # Try Qt clipboard (ground truth for the app, helpful in tray mode)
    if _copy_text_via_qt(text):
        success = True

    # Also try subprocess-based clipboard (persists after exit, essential for one-shot)
    if _copy_text_via_subprocess(text):
        success = True

    return success


def get_text_from_clipboard() -> str | None:
    """Read text from the system clipboard.

    Tries subprocess tools (wl-paste, xclip, xsel) first, falls back to Qt.

    Returns:
        The text content of the clipboard, or None if empty/unavailable.
    """
    # Try subprocess tools
    text = _get_text_via_subprocess()
    if text is not None:
        return text

    # Fall back to Qt
    return _get_text_via_qt()

def _copy_text_via_qt(text: str) -> bool:
    """Copy text via Qt's QClipboard."""
    app = cast(QGuiApplication, QGuiApplication.instance())
    if app is None:
        logger.error("No QGuiApplication instance — cannot access clipboard")
        return False

    clipboard = app.clipboard()
    if clipboard is None:
        logger.error("Clipboard not available")
        return False

    try:
        clipboard.setText(text)
        logger.debug("Text copied to clipboard via Qt: %s", text[:80])
        return True
    except Exception as e:
        logger.error("Failed to copy text to clipboard: %s", e)
        return False


# --- Private implementation ---


def get_image_from_clipboard() -> QImage | None:
    """Read an image from the system clipboard.

    Returns:
        The QImage content of the clipboard, or None if empty/unavailable.
    """
    # Try subprocess tools
    img_data = _get_image_via_subprocess()
    if img_data:
        qimg = QImage.fromData(img_data)
        if not qimg.isNull():
            return qimg

    # Fall back to Qt
    return _get_image_via_qt()


def _image_to_png_bytes(image: QImage) -> bytes | None:
    """Convert a QImage to PNG bytes in memory."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):  # type: ignore[call-overload]
        logger.error("Failed to encode image as PNG for clipboard")
        return None
    ba: QByteArray = buffer.data()
    return bytes(ba.data())


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
    if (session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY")) and _try_clipboard_cmd(["wl-copy", "--type", "image/png"], png_data):
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


def _copy_text_via_subprocess(text: str) -> bool:
    """Try to copy text via subprocess clipboard tools.

    Attempts tools in order: wl-copy (Wayland), xclip (X11), xsel (X11).
    These tools fork daemon processes that keep serving the clipboard
    data after our threaded background upload completes.
    """
    text_data = text.encode("utf-8")
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()

    # On Wayland, try wl-copy first
    if (session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY")) and _try_clipboard_cmd(["wl-copy", "--type", "text/plain"], text_data):
        return True

    # On X11 (or as fallback), try xclip then xsel
    # Try multiple targets for xclip to improve compatibility
    for target in ["UTF8_STRING", "text/plain", "STRING"]:
        if _try_clipboard_cmd(
            ["xclip", "-selection", "clipboard", "-target", target, "-i"],
            text_data,
        ):
            return True

    return _try_clipboard_cmd(
        ["xsel", "--clipboard", "--input"],
        text_data,
    )


def _get_text_via_subprocess() -> str | None:
    """Read text via subprocess clipboard tools."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()

    # On Wayland, try wl-paste
    if (session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY")) and shutil.which("wl-paste"):
        try:
            res = subprocess.run(
                ["wl-paste", "--type", "text/plain", "--no-newline"],
                capture_output=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.decode("utf-8")
        except Exception as e:
            logger.debug("wl-paste failed: %s", e)

    # On X11, try xclip
    if shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.decode("utf-8")
        except Exception as e:
            logger.debug("xclip -o failed: %s", e)

    # Try xsel
    if shutil.which("xsel"):
        try:
            res = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.decode("utf-8")
        except Exception as e:
            logger.debug("xsel -o failed: %s", e)

    return None


def _get_text_via_qt() -> str | None:
    """Read text via Qt's QClipboard."""
    app = cast(QGuiApplication, QGuiApplication.instance())
    if app is None:
        return None

    clipboard = app.clipboard()
    if clipboard is None:
        return None

    try:
        return clipboard.text()
    except Exception as e:
        logger.debug("Qt clipboard read failed: %s", e)
        return None


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
        assert proc.stdin is not None
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


    return None


def _get_image_via_subprocess() -> bytes | None:
    """Read image bytes via subprocess clipboard tools."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()

    # On Wayland, try wl-paste
    if (session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY")) and shutil.which("wl-paste"):
        try:
            res = subprocess.run(
                ["wl-paste", "--type", "image/png"],
                capture_output=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception as e:
            logger.debug("wl-paste (image) failed: %s", e)

    # On X11, try xclip
    if shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", "clipboard", "-target", "image/png", "-o"],
                capture_output=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception as e:
            logger.debug("xclip (image) failed: %s", e)

    return None


def _get_image_via_qt() -> QImage | None:
    """Read image via Qt's QClipboard."""
    app = cast(QGuiApplication, QGuiApplication.instance())
    if app is None:
        return None

    clipboard = app.clipboard()
    if clipboard is None:
        return None

    try:
        img = clipboard.image()
        if not img.isNull():
            return img
    except Exception as e:
        logger.debug("Qt clipboard image read failed: %s", e)
    return None


def _copy_image_via_qt(image: QImage) -> bool:
    """
    Copy image via Qt's QClipboard.
    Works reliably when the app stays alive (tray mode). In one-shot
    mode on Wayland, the clipboard data may be lost when the process exits.
    """
    app = cast(QGuiApplication, QGuiApplication.instance())
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
