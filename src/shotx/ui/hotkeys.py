"""Global hotkey management for ShotX.

Handles system-wide keyboard shortcuts that work even when ShotX is
not focused. Uses a tiered approach:

1. Wayland: org.freedesktop.portal.GlobalShortcuts D-Bus interface
2. X11: Direct key grab via xcb (placeholder — uses QShortcut for now)
3. Fallback: Users set up shortcuts via their DE settings, ShotX listens
   for CLI invocations (--capture-fullscreen, etc.)

For the MVP, we use a simplified approach that works across both:
- Register shortcuts via Qt's QShortcut on a hidden window
- This works when the app has an active window but not system-wide
- System-wide shortcuts require per-DE setup (documented in README)
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget, QShortcut

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Manages global keyboard shortcuts.

    For the MVP, this provides a simple interface to register shortcuts.
    The actual system-wide key grab will be enhanced in later phases.
    """

    def __init__(self) -> None:
        self._shortcuts: list[QShortcut] = []
        # Hidden widget to own the shortcuts
        self._widget: QWidget | None = None

    def register(
        self,
        key_sequence: str,
        callback: Callable[[], None],
        description: str = "",
    ) -> bool:
        """Register a keyboard shortcut.

        Args:
            key_sequence: Key sequence string (e.g., "Print", "Ctrl+Print").
            callback: Function to call when the shortcut is triggered.
            description: Human-readable description for logging.

        Returns:
            True if registration succeeded.
        """
        if self._widget is None:
            self._widget = QWidget()
            self._widget.setWindowFlags(Qt.WindowType.Tool)
            # Don't show the widget — it's just a parent for shortcuts

        try:
            shortcut = QShortcut(QKeySequence(key_sequence), self._widget)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

            logger.info("Registered hotkey: %s (%s)", key_sequence, description)
            return True

        except Exception as e:
            logger.error("Failed to register hotkey '%s': %s", key_sequence, e)
            return False

    def unregister_all(self) -> None:
        """Remove all registered shortcuts."""
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
        self._shortcuts.clear()
        logger.info("All hotkeys unregistered")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.unregister_all()
        if self._widget is not None:
            self._widget.close()
            self._widget = None
