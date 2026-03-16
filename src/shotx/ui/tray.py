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

        Tries the bundled asset first, falls back to a system theme icon.
        """
        import importlib.resources as pkg_resources
        
        try:
            icon_path = pkg_resources.files("shotx.assets").joinpath("shotx.png")
            if icon_path.exists():
                self._tray.setIcon(QIcon(str(icon_path)))
                logger.debug("Using bundled tray icon: %s", icon_path)
                return
        except Exception as e:
            logger.warning("Failed to load bundled tray icon: %s", e)

        # Fallback to system theme icon
        icon = QIcon.fromTheme("camera-photo")
        if icon.isNull():
            icon = QIcon.fromTheme("applets-screenshooter")
        self._tray.setIcon(icon)
        logger.debug("Using system theme icon")

    def _setup_menu(self) -> None:
        """Build the categorized right-click context menu."""

        # ---------------------------------------------------------
        # 0. Open Main Window (top of menu, like ShareX)
        # ---------------------------------------------------------
        open_main = QAction("🏠 Open ShotX", self._menu)
        open_main.triggered.connect(self._on_open_main_window)
        self._menu.addAction(open_main)
        self._menu.addSeparator()

        # ---------------------------------------------------------
        # 1. Capture Submenu
        # ---------------------------------------------------------
        capture_menu = self._menu.addMenu("📷 Capture")

        capture_fullscreen = QAction("Capture Fullscreen", self._menu)
        capture_fullscreen.setShortcut("Print")
        capture_fullscreen.triggered.connect(self._on_capture_fullscreen)
        capture_menu.addAction(capture_fullscreen)

        capture_region = QAction("Capture Region", self._menu)
        capture_region.setShortcut("Ctrl+Print")
        capture_region.triggered.connect(self._on_capture_region)
        capture_menu.addAction(capture_region)

        capture_window = QAction("Capture Window", self._menu)
        capture_window.setShortcut("Alt+Print")
        capture_window.triggered.connect(self._on_capture_region)
        capture_menu.addAction(capture_window)

        capture_menu.addSeparator()

        self._record_mp4_action = QAction("Record Screen (MP4)", self._menu)
        self._record_mp4_action.triggered.connect(self._on_record_mp4)
        capture_menu.addAction(self._record_mp4_action)

        self._record_gif_action = QAction("Record Screen (GIF)", self._menu)
        self._record_gif_action.triggered.connect(self._on_record_gif)
        capture_menu.addAction(self._record_gif_action)

        self._stop_record_action = QAction("Stop Recording", self._menu)
        self._stop_record_action.triggered.connect(self._on_stop_record)
        self._stop_record_action.setVisible(False)
        self._stop_record_action.setShortcut("Shift+Print")
        capture_menu.addAction(self._stop_record_action)

        capture_menu.addSeparator()

        capture_ocr = QAction("Extract Text (OCR)", self._menu)
        capture_ocr.triggered.connect(self._on_capture_ocr)
        capture_menu.addAction(capture_ocr)

        # ---------------------------------------------------------
        # 2. Tools Submenu
        # ---------------------------------------------------------
        tools_menu = self._menu.addMenu("🛠️ Tools")

        editor_tool = QAction("Image Editor", self._menu)
        editor_tool.triggered.connect(self._on_image_editor)
        tools_menu.addAction(editor_tool)
        
        tools_menu.addSeparator()

        pin_region = QAction("Pin to Screen", self._menu)
        pin_region.triggered.connect(self._on_pin_region)
        tools_menu.addAction(pin_region)

        capture_color = QAction("Color Picker", self._menu)
        capture_color.triggered.connect(self._on_capture_color_picker)
        tools_menu.addAction(capture_color)

        capture_ruler = QAction("Screen Ruler", self._menu)
        capture_ruler.triggered.connect(self._on_capture_ruler)
        tools_menu.addAction(capture_ruler)

        tools_menu.addSeparator()

        qr_scan = QAction("QR Code Scanner", self._menu)
        qr_scan.triggered.connect(self._on_qr_scan)
        tools_menu.addAction(qr_scan)

        qr_generate = QAction("Generate QR from Clipboard", self._menu)
        qr_generate.triggered.connect(self._on_qr_generate)
        tools_menu.addAction(qr_generate)

        qr_scan_clipboard = QAction("Scan QR from Clipboard Image", self._menu)
        qr_scan_clipboard.triggered.connect(self._on_qr_scan_clipboard)
        tools_menu.addAction(qr_scan_clipboard)

        tools_menu.addSeparator()

        shorten_url = QAction("Shorten URL from Clipboard", self._menu)
        shorten_url.triggered.connect(self._on_shorten_url_clipboard)
        tools_menu.addAction(shorten_url)

        tools_menu.addSeparator()

        hash_tool = QAction("Hash Checker", self._menu)
        hash_tool.triggered.connect(self._on_hash_checker)
        tools_menu.addAction(hash_tool)

        indexer_tool = QAction("Directory Indexer", self._menu)
        indexer_tool.triggered.connect(self._on_directory_indexer)
        tools_menu.addAction(indexer_tool)

        self._menu.addSeparator()

        # ---------------------------------------------------------
        # 3. Base application actions
        # ---------------------------------------------------------
        open_folder_action = QAction("📂 Screenshots Folder", self._menu)
        open_folder_action.triggered.connect(self._on_open_folder)
        self._menu.addAction(open_folder_action)

        history_action = QAction("📋 History", self._menu)
        history_action.triggered.connect(self._on_history)
        self._menu.addAction(history_action)

        settings_action = QAction("⚙️ Settings", self._menu)
        settings_action.triggered.connect(self._on_settings)
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

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
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double click → open Main Window
            self._on_open_main_window()
        # Right click is handled by the context menu automatically

    def _on_capture_fullscreen(self) -> None:
        """Trigger fullscreen capture."""
        # 300ms delay to give the Qt Menu time to hide before the compositor snaps
        QTimer.singleShot(300, self._app.capture_fullscreen)

    def _on_capture_region(self) -> None:
        """Trigger region capture overlay."""
        QTimer.singleShot(300, self._app.capture_region)

    def _on_capture_ocr(self) -> None:
        """Trigger OCR region capture."""
        QTimer.singleShot(300, self._app.capture_ocr)

    def _on_pin_region(self) -> None:
        """Trigger Pin to Screen region capture."""
        QTimer.singleShot(300, self._app.pin_region)

    def _on_capture_color_picker(self) -> None:
        """Trigger Color Picker overlay."""
        QTimer.singleShot(300, self._app.capture_color_picker)

    def _on_capture_ruler(self) -> None:
        """Trigger Screen Ruler overlay."""
        QTimer.singleShot(300, self._app.capture_ruler)

    def _on_qr_scan(self) -> None:
        """Trigger QR code scanner."""
        QTimer.singleShot(300, self._app.capture_qr_scan)

    def _on_qr_generate(self) -> None:
        """Trigger QR generation from clipboard."""
        # No delay needed for generation as it doesn't capture screen
        self._app.generate_qr_from_clipboard()

    def _on_qr_scan_clipboard(self) -> None:
        """Trigger QR scan from clipboard image."""
        self._app.scan_qr_from_clipboard()

    def _on_open_main_window(self) -> None:
        """Open the unified ShotX Main Window."""
        self._app.open_main_window()

    def _on_history(self) -> None:
        """Trigger history viewer."""
        self._app.open_history_viewer()

    def _on_settings(self) -> None:
        """Open the Application Settings dialog."""
        self._app.open_settings_dialog()

    def _on_shorten_url_clipboard(self) -> None:
        """Trigger URL shortening from clipboard."""
        self._app.shorten_clipboard_url()

    def _on_hash_checker(self) -> None:
        """Trigger hash checker tool."""
        self._app.open_hash_checker()

    def _on_directory_indexer(self) -> None:
        """Trigger directory indexer tool."""
        self._app.open_directory_indexer()

    def _on_image_editor(self) -> None:
        """Handler for opening the Image Editor."""
        self._app.open_image_editor()

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
        """Handle fallback Qt notification clicks (if DBus failed)."""
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
