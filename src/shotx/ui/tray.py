"""System tray icon for ShotX.

Provides a persistent system tray icon with a right-click context menu
for quick access to capture functions, screenshot folder, and settings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from shotx.ui.notification import open_folder

if TYPE_CHECKING:
    from shotx.app import ShotXApp

logger = logging.getLogger(__name__)


class TrayIcon:
    """System tray icon with context menu for ShotX.

    The tray icon is the primary interface for the app when running
    in background mode. Left-click triggers fullscreen capture,
    right-click shows the context menu.
    """

    def __init__(self, app: ShotXApp) -> None:
        self._app = app
        self._tray = QSystemTrayIcon()
        self._menu = QMenu()

        self._setup_icon()
        self._setup_menu()
        self._setup_signals()

    @property
    def tray_icon(self) -> QSystemTrayIcon:
        """Access the underlying QSystemTrayIcon (for notifications)."""
        return self._tray

    def show(self) -> None:
        """Show the tray icon."""
        self._tray.show()
        logger.info("Tray icon shown")

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray.hide()

    def _setup_icon(self) -> None:
        """Set the tray icon image.

        Tries the bundled icon first, falls back to a system theme icon.
        """
        # Try bundled icon
        icon_paths = [
            Path(__file__).parent.parent.parent.parent / "resources" / "icons" / "shotx-tray.svg",
            Path(__file__).parent.parent.parent.parent / "resources" / "icons" / "shotx.svg",
        ]

        for icon_path in icon_paths:
            if icon_path.exists():
                self._tray.setIcon(QIcon(str(icon_path)))
                logger.debug("Using icon: %s", icon_path)
                return

        # Fallback to system theme icon
        icon = QIcon.fromTheme("camera-photo")
        if icon.isNull():
            icon = QIcon.fromTheme("applets-screenshooter")
        self._tray.setIcon(icon)
        logger.debug("Using system theme icon")

    def _setup_menu(self) -> None:
        """Build the right-click context menu."""
        # Capture actions
        capture_fullscreen = QAction("📷 Capture Fullscreen", self._menu)
        capture_fullscreen.setShortcut("Print")
        capture_fullscreen.triggered.connect(self._on_capture_fullscreen)
        self._menu.addAction(capture_fullscreen)

        capture_region = QAction("📐 Capture Region", self._menu)
        capture_region.setShortcut("Ctrl+Print")
        capture_region.triggered.connect(self._on_capture_region)
        self._menu.addAction(capture_region)

        capture_window = QAction("🪟 Capture Window", self._menu)
        capture_window.setShortcut("Alt+Print")
        capture_window.triggered.connect(self._on_capture_region)  # Same overlay
        self._menu.addAction(capture_window)

        self._menu.addSeparator()

        # Recording actions
        self._record_mp4_action = QAction("📹 Record Screen (MP4)", self._menu)
        self._record_mp4_action.triggered.connect(self._on_record_mp4)
        self._menu.addAction(self._record_mp4_action)

        self._record_gif_action = QAction("🎞️ Record Screen (GIF)", self._menu)
        self._record_gif_action.triggered.connect(self._on_record_gif)
        self._menu.addAction(self._record_gif_action)

        self._stop_record_action = QAction("🛑 Stop Recording", self._menu)
        self._stop_record_action.triggered.connect(self._on_stop_record)
        self._stop_record_action.setVisible(False)
        self._stop_record_action.setShortcut("Shift+Print") # Basic stop hotkey
        self._menu.addAction(self._stop_record_action)

        self._menu.addSeparator()

        # File actions
        open_folder_action = QAction("📂 Open Screenshots Folder", self._menu)
        open_folder_action.triggered.connect(self._on_open_folder)
        self._menu.addAction(open_folder_action)

        history_action = QAction("📋 History", self._menu)
        history_action.setEnabled(False)  # Phase 8
        self._menu.addAction(history_action)

        self._menu.addSeparator()

        # Settings & quit
        settings_action = QAction("⚙️  Settings", self._menu)
        settings_action.setEnabled(False)  # Phase 8
        self._menu.addAction(settings_action)

        quit_action = QAction("❌ Quit", self._menu)
        quit_action.triggered.connect(self._on_quit)
        self._menu.addAction(quit_action)

        self._tray.setContextMenu(self._menu)
        self._tray.setToolTip("ShotX — Screenshot Tool")

    def _setup_signals(self) -> None:
        """Connect tray icon signals."""
        # Left click = quick capture fullscreen
        self._tray.activated.connect(self._on_activated)
        # Click on notification = open last file
        self._tray.messageClicked.connect(self._on_notification_clicked)

    # --- Signal handlers ---

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (clicks)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left click → capture fullscreen
            self._on_capture_fullscreen()
        # Right click is handled by the context menu automatically

    def _on_capture_fullscreen(self) -> None:
        """Trigger fullscreen capture."""
        # 300ms delay to give the Qt Menu time to hide before the compositor snaps
        QTimer.singleShot(300, self._app.capture_fullscreen)

    def _on_capture_region(self) -> None:
        """Trigger region capture overlay."""
        QTimer.singleShot(300, self._app.capture_region)

    def _on_record_mp4(self) -> None:
        self._app.start_recording("mp4")

    def _on_record_gif(self) -> None:
        self._app.start_recording("gif")
        
    def _on_stop_record(self) -> None:
        self._app.stop_recording()

    def set_recording_state(self, is_recording: bool) -> None:
        """Update tray menu for recording state."""
        self._record_mp4_action.setVisible(not is_recording)
        self._record_gif_action.setVisible(not is_recording)
        self._stop_record_action.setVisible(is_recording)
        
        if is_recording:
            # Try to grab a standard recording icon
            icon = QIcon.fromTheme("media-record")
            if not icon.isNull():
                self._tray.setIcon(icon)
        else:
            self._setup_icon()

    def _on_open_folder(self) -> None:
        """Open the screenshots folder in file manager."""
        output_dir = Path(self._app.settings.capture.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        open_folder(output_dir)

    def _on_notification_clicked(self) -> None:
        """Handle notification click — open the last captured file."""
        last_file = self._app.last_saved_path
        if last_file and last_file.exists():
            from shotx.ui.notification import open_file
            open_file(last_file)

    def _on_quit(self) -> None:
        """Quit the application."""
        logger.info("Quit requested from tray menu")
        self._tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
