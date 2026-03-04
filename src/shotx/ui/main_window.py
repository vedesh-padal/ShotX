"""ShotX Main Window — unified hub mirroring the ShareX Main Window.

Left sidebar provides categorized menus (Capture, Upload, Tools) and
quick-access items (Settings, History, Screenshots folder).
Center panel permanently displays the History viewer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QMenu,
    QSizePolicy,
    QFrame,
    QLabel,
)

from shotx.ui.history import HistoryWidget
from shotx.ui.notification import open_folder

if TYPE_CHECKING:
    from shotx.app import ShotXApp

logger = logging.getLogger(__name__)

# Sidebar button width
_SIDEBAR_WIDTH = 180


class _SidebarButton(QPushButton):
    """A flat, left-aligned sidebar button with optional submenu arrow."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding: 4px 12px;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.14);
            }
            QPushButton::menu-indicator {
                subcontrol-position: right center;
                subcontrol-origin: padding;
                right: 8px;
            }
            QMenu {
                background-color: #2b2d31;
                border: 1px solid #404249;
                border-radius: 6px;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 24px;
                color: #dcddde;
                border-radius: 3px;
                margin: 1px 4px;
            }
            QMenu::item:selected {
                background-color: #4752c4;
                color: #ffffff;
            }
            QMenu::item:pressed {
                background-color: #3c45a5;
            }
            QMenu::item:disabled {
                color: #72767d;
            }
            QMenu::separator {
                height: 1px;
                background: #404249;
                margin: 4px 8px;
            }
            QMenu::indicator {
                width: 14px;
                height: 14px;
                margin-left: 6px;
            }
            """
        )


class _SidebarSeparator(QFrame):
    """A thin horizontal line separator for the sidebar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setFixedHeight(1)
        self.setStyleSheet("color: rgba(255, 255, 255, 0.12);")


class ShotXMainWindow(QMainWindow):
    """Unified application hub mirroring the ShareX Main Window."""

    def __init__(self, app: ShotXApp, parent=None):
        super().__init__(parent)
        self._app = app

        self.setWindowTitle("ShotX")
        self.resize(1050, 650)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- Left Sidebar ----
        sidebar = QWidget()
        sidebar.setFixedWidth(_SIDEBAR_WIDTH)
        sidebar.setStyleSheet(
            """
            QWidget {
                background-color: #2b2d31;
            }
            """
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 8, 6, 8)
        sidebar_layout.setSpacing(2)

        # -- Capture submenu --
        btn_capture = _SidebarButton("📷  Capture")
        capture_menu = QMenu(btn_capture)
        self._populate_capture_menu(capture_menu)
        btn_capture.setMenu(capture_menu)
        sidebar_layout.addWidget(btn_capture)

        # -- Upload submenu --
        btn_upload = _SidebarButton("⬆️  Upload")
        upload_menu = QMenu(btn_upload)
        self._populate_upload_menu(upload_menu)
        btn_upload.setMenu(upload_menu)
        sidebar_layout.addWidget(btn_upload)

        # -- Tools submenu --
        btn_tools = _SidebarButton("🛠️  Tools")
        tools_menu = QMenu(btn_tools)
        self._populate_tools_menu(tools_menu)
        btn_tools.setMenu(tools_menu)
        sidebar_layout.addWidget(btn_tools)

        sidebar_layout.addWidget(_SidebarSeparator())

        # -- After capture tasks submenu (checkable) --
        btn_after_capture = _SidebarButton("📋  After capture tasks")
        self._after_capture_menu = QMenu(btn_after_capture)
        self._populate_after_capture_menu(self._after_capture_menu)
        btn_after_capture.setMenu(self._after_capture_menu)
        sidebar_layout.addWidget(btn_after_capture)

        # -- Destinations submenu (radio) --
        btn_destinations = _SidebarButton("☁️  Destinations")
        self._dest_menu = QMenu(btn_destinations)
        self._populate_destinations_menu(self._dest_menu)
        btn_destinations.setMenu(self._dest_menu)
        sidebar_layout.addWidget(btn_destinations)

        sidebar_layout.addWidget(_SidebarSeparator())

        # -- Settings links --
        btn_app_settings = _SidebarButton("⚙️  Application settings...")
        btn_app_settings.clicked.connect(self._on_app_settings)
        sidebar_layout.addWidget(btn_app_settings)

        btn_task_settings = _SidebarButton("📝  Task settings...")
        btn_task_settings.clicked.connect(self._on_task_settings)
        sidebar_layout.addWidget(btn_task_settings)

        btn_hotkey_settings = _SidebarButton("⌨️  Hotkey settings...")
        btn_hotkey_settings.setEnabled(False)  # Future phase
        sidebar_layout.addWidget(btn_hotkey_settings)

        sidebar_layout.addWidget(_SidebarSeparator())

        # -- Quick actions --
        btn_screenshots = _SidebarButton("📁  Screenshots folder...")
        btn_screenshots.clicked.connect(self._on_open_folder)
        sidebar_layout.addWidget(btn_screenshots)

        btn_history = _SidebarButton("🕒  History...")
        btn_history.clicked.connect(self._on_history_refresh)
        sidebar_layout.addWidget(btn_history)

        btn_image_history = _SidebarButton("🖼️  Image history...")
        btn_image_history.setEnabled(False)  # Future phase
        sidebar_layout.addWidget(btn_image_history)

        sidebar_layout.addWidget(_SidebarSeparator())

        btn_about = _SidebarButton("ℹ️  About...")
        btn_about.clicked.connect(self._on_about)
        sidebar_layout.addWidget(btn_about)

        sidebar_layout.addStretch()

        root_layout.addWidget(sidebar)

        # ---- Center Panel: History ----
        self._history_widget = HistoryWidget(self._app, self)
        root_layout.addWidget(self._history_widget, stretch=1)

    # ------------------------------------------------------------------
    # Menu Builders
    # ------------------------------------------------------------------

    def _populate_capture_menu(self, menu: QMenu) -> None:
        a = menu.addAction("Fullscreen")
        a.triggered.connect(lambda: self._app.capture_fullscreen())

        a = menu.addAction("Region")
        a.triggered.connect(lambda: self._app.capture_region())

        a = menu.addAction("Window")
        a.triggered.connect(lambda: self._app.capture_region())

        menu.addSeparator()

        a = menu.addAction("Screen Recording (MP4)")
        a.triggered.connect(lambda: self._app.start_recording("mp4"))

        a = menu.addAction("Screen Recording (GIF)")
        a.triggered.connect(lambda: self._app.start_recording("gif"))

        menu.addSeparator()

        a = menu.addAction("Extract Text (OCR)")
        a.triggered.connect(lambda: self._app.capture_ocr())

    def _populate_upload_menu(self, menu: QMenu) -> None:
        a = menu.addAction("Upload File...")
        a.triggered.connect(self._on_upload_file)

        a = menu.addAction("Upload from Clipboard...")
        a.triggered.connect(self._on_upload_clipboard)

        menu.addSeparator()

        a = menu.addAction("Shorten URL from Clipboard")
        a.triggered.connect(self._on_shorten_url_clipboard)

    def _populate_tools_menu(self, menu: QMenu) -> None:
        a = menu.addAction("Image Editor")
        a.triggered.connect(lambda: self._app.open_image_editor())

        menu.addSeparator()

        a = menu.addAction("Pin to Screen")
        a.triggered.connect(lambda: self._app.pin_region())

        a = menu.addAction("Color Picker")
        a.triggered.connect(lambda: self._app.capture_color_picker())

        a = menu.addAction("Screen Ruler")
        a.triggered.connect(lambda: self._app.capture_ruler())

        menu.addSeparator()

        a = menu.addAction("QR Code Scanner")
        a.triggered.connect(lambda: self._app.capture_qr_scan())

        a = menu.addAction("Generate QR from Clipboard")
        a.triggered.connect(lambda: self._app.generate_qr_from_clipboard())

        a = menu.addAction("Scan QR from Clipboard Image")
        a.triggered.connect(lambda: self._app.scan_qr_from_clipboard())

        menu.addSeparator()

        a = menu.addAction("Hash Checker")
        a.triggered.connect(lambda: self._app.open_hash_checker())

        a = menu.addAction("Directory Indexer")
        a.triggered.connect(lambda: self._app.open_directory_indexer())

    def _populate_after_capture_menu(self, menu: QMenu) -> None:
        """Build checkable menu items that read/write settings."""
        workflow = self._app.settings.workflow

        save = workflow.save_to_file
        copy = workflow.copy_to_clipboard
        upload = workflow.upload_image
        open_editor = workflow.open_in_editor

        self._ac_save = menu.addAction("Save image to file")
        self._ac_save.setCheckable(True)
        self._ac_save.setChecked(save)
        self._ac_save.toggled.connect(
            lambda v: self._set_after_capture("save_to_file", v)
        )

        self._ac_copy = menu.addAction("Copy image to clipboard")
        self._ac_copy.setCheckable(True)
        self._ac_copy.setChecked(copy)
        self._ac_copy.toggled.connect(
            lambda v: self._set_after_capture("copy_to_clipboard", v)
        )

        self._ac_upload = menu.addAction("Upload image to host")
        self._ac_upload.setCheckable(True)
        self._ac_upload.setChecked(upload)
        self._ac_upload.toggled.connect(
            lambda v: self._set_after_capture("upload_image", v)
        )

        self._ac_editor = menu.addAction("Open in image editor")
        self._ac_editor.setCheckable(True)
        self._ac_editor.setChecked(open_editor)
        self._ac_editor.toggled.connect(
            lambda v: self._set_after_capture("open_in_editor", v)
        )

    def _populate_destinations_menu(self, menu: QMenu) -> None:
        """Build radio-style destination selector."""
        settings = self._app.settings
        current_dest = getattr(settings, "upload_destination", "imgur")

        self._dest_actions: dict[str, QAction] = {}  # key → QAction
        destinations = [
            ("Imgur", "imgur"),
            ("Tmpfiles.org", "tmpfiles"),
            ("ImgBB", "imgbb"),
            ("Amazon S3", "s3"),
            ("FTP / SFTP", "ftp"),
            ("Custom Uploader", "custom"),
        ]

        for label, key in destinations:
            a = menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(current_dest == key)
            a.triggered.connect(lambda checked, k=key: self._set_destination(k))
            self._dest_actions[key] = a

    # ------------------------------------------------------------------
    # Settings Mutators
    # ------------------------------------------------------------------

    def _set_after_capture(self, key: str, value: bool) -> None:
        """Update a single after_capture boolean flag in workflow settings."""
        setattr(self._app.settings.workflow, key, value)
        self._app._settings_manager.save()
        logger.debug("after_capture.%s = %s (saved)", key, value)

    def _set_destination(self, key: str) -> None:
        """Set the active upload destination and persist."""
        self._app.settings.upload_destination = key
        self._app._settings_manager.save()
        logger.debug("upload_destination = %s (saved)", key)

        # Radio behavior: check only the selected action
        for k, action in self._dest_actions.items():
            action.setChecked(k == key)

    # ------------------------------------------------------------------
    # Action Handlers
    # ------------------------------------------------------------------

    def _on_app_settings(self) -> None:
        """Open Application Settings dialog."""
        from shotx.ui.settings_dialog import ApplicationSettingsDialog
        
        dialog = ApplicationSettingsDialog(self._app._settings_manager, self)
        if dialog.exec():
            # Refresh anything in the UI that depends on settings
            self._after_capture_menu.clear()
            self._populate_after_capture_menu(self._after_capture_menu)
            
            self._dest_menu.clear()
            self._populate_destinations_menu(self._dest_menu)

    def _on_task_settings(self) -> None:
        """Open Task Settings dialog."""
        from shotx.ui.task_settings_dialog import TaskSettingsDialog

        dialog = TaskSettingsDialog(self._app._settings_manager, self)
        dialog.exec()

    def _on_open_folder(self) -> None:
        """Open the screenshots output folder in the file manager."""
        from pathlib import Path

        output_dir = Path(self._app.settings.capture.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        open_folder(output_dir)

    def _on_history_refresh(self) -> None:
        """Refresh the embedded history table."""
        self._history_widget._load_data(clear=True)

    def _on_upload_file(self) -> None:
        """Open a file dialog and upload the selected image."""
        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select image to upload",
            str(Path(self._app.settings.capture.output_dir).expanduser()),
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)",
        )
        if path:
            self._app._start_background_upload(Path(path))

    def _on_upload_clipboard(self) -> None:
        """Upload the current clipboard image."""
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtGui import QImage
        from pathlib import Path
        import tempfile

        clipboard = QApplication.clipboard()
        img = clipboard.image()

        if img.isNull():
            QMessageBox.warning(
                self, "No Image", "The clipboard does not contain an image."
            )
            return

        # Save to a temp file then upload
        tmp = Path(tempfile.mktemp(suffix=".png", prefix="shotx_clipboard_"))
        img.save(str(tmp))
        self._app._start_background_upload(tmp)

    def _on_shorten_url_clipboard(self) -> None:
        """Shorten any URL currently in the clipboard."""
        self._app.shorten_clipboard_url()

    def _on_about(self) -> None:
        """Show a simple About dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

        dlg = QDialog(self)
        dlg.setWindowTitle("About ShotX")
        dlg.setFixedSize(400, 225)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(8)

        title = QLabel("<b style='font-size:16px;'>ShotX</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        desc = QLabel(
            "A full-featured ShareX clone for Linux.<br><br>"
            "Built with Python + PySide6 (Qt6).<br>"
            "Wayland-first, X11 fallback.<br><br>"
            "© 2026 Vedesh Padal"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        btn = QPushButton("OK")
        btn.setFixedWidth(80)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dlg.exec()
