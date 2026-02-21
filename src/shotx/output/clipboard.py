"""Clipboard operations for ShotX.

Copies captured images to the system clipboard using Qt6's clipboard
abstraction. Works on both X11 and Wayland — Qt6 handles the protocol
differences internally (X11 selections vs wl-copy).
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QGuiApplication, QImage

logger = logging.getLogger(__name__)


def copy_image_to_clipboard(image: QImage) -> bool:
    """Copy a QImage to the system clipboard.

    Args:
        image: The image to copy.

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
        clipboard.setImage(image)
        logger.debug("Image copied to clipboard (%dx%d)", image.width(), image.height())
        return True
    except Exception as e:
        logger.error("Failed to copy image to clipboard: %s", e)
        return False


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard.

    Useful for copying file paths or upload URLs after capture.

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
