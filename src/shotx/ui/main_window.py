"""ShotX Main Window — unified hub mirroring the ShareX Main Window.

Left sidebar provides categorized menus (Capture, Upload, Tools) and
quick-access items (Settings, History, Screenshots folder).
Center panel permanently displays the Image History thumbnail grid.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shotx.ui.about import ShotXAboutDialog
from shotx.ui.image_history import ImageHistoryWidget
from shotx.ui.notification import open_folder
from shotx.ui.theme import Theme

if TYPE_CHECKING:
    from shotx.app import ShotXApp

logger = logging.getLogger(__name__)

# Sidebar button width
_SIDEBAR_WIDTH = 200


class _SidebarButton(QPushButton):
    """A flat, left-aligned sidebar button with optional submenu arrow."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(Theme.get_sidebar_qss(font_size=14))


class _SidebarSeparator(QFrame):
    """A thin horizontal line separator for the sidebar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setFixedHeight(1)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); border: none;")


class ShotXMainWindow(QMainWindow):
    """Unified application hub mirroring the ShareX Main Window."""

    def __init__(self, app: ShotXApp, parent=None):
        super().__init__(parent)
        self._app = app

        self.setWindowTitle("ShotX")
        self.resize(1130, 700)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        # Apply main window styles (global level for the hub)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Theme.BASE_DARK};
            }}
            QStatusBar {{
                background-color: {Theme.BASE_DARK};
                color: {Theme.TEXT_MUTED};
                border-top: 1px solid rgba(255, 255, 255, 0.05);
            }}
        """)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- Left Sidebar ----
        sidebar = QWidget()
        sidebar.setFixedWidth(_SIDEBAR_WIDTH)
        sidebar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {Theme.BASE_DARK};
                border-right: 1px solid rgba(255, 255, 255, 0.05);
            }}
            """
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 6, 8)
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
        btn_hotkey_settings.clicked.connect(self._on_hotkey_settings)
        sidebar_layout.addWidget(btn_hotkey_settings)

        sidebar_layout.addWidget(_SidebarSeparator())

        # -- Quick actions --
        btn_screenshots = _SidebarButton("📁  Screenshots folder...")
        btn_screenshots.clicked.connect(self._on_open_folder)
        sidebar_layout.addWidget(btn_screenshots)

        btn_history = _SidebarButton("🕒  History...")
        btn_history.clicked.connect(self._on_open_history)
        sidebar_layout.addWidget(btn_history)

        btn_image_history = _SidebarButton("🖼️  Image history")
        btn_image_history.clicked.connect(self._on_image_history_refresh)
        sidebar_layout.addWidget(btn_image_history)

        sidebar_layout.addWidget(_SidebarSeparator())

        btn_about = _SidebarButton("ℹ️  About...")
        btn_about.clicked.connect(self._on_about)
        sidebar_layout.addWidget(btn_about)

        sidebar_layout.addStretch()

        root_layout.addWidget(sidebar)

        # ---- Center Panel: Image History (thumbnail grid) ----
        self._image_history_widget = ImageHistoryWidget(self._app, self)
        root_layout.addWidget(self._image_history_widget, stretch=1)

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

        a = menu.addAction("Shorten URL from Clipboard")
        a.triggered.connect(self._on_shorten_url_clipboard)

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
        current_dest = settings.upload.default_uploader.lower()

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
        self._app.settings.upload.default_uploader = key
        self._app._settings_manager.save()
        logger.debug("upload.default_uploader = %s (saved)", key)

        # Radio behavior: check only the selected action
        for k, action in self._dest_actions.items():
            action.setChecked(k == key)

    # ------------------------------------------------------------------
    # Action Handlers
    # ------------------------------------------------------------------

    def _on_app_settings(self) -> None:
        """Open Application Settings dialog."""
        from shotx.ui.settings_dialog import ApplicationSettingsDialog

        dialog = ApplicationSettingsDialog(self._app._settings_manager, start_page=0, parent=self)
        if dialog.exec():
            # Refresh anything in the UI that depends on settings
            self._app.apply_hotkeys()
            self._after_capture_menu.clear()
            self._populate_after_capture_menu(self._after_capture_menu)

            self._dest_menu.clear()
            self._populate_destinations_menu(self._dest_menu)

    def _on_hotkey_settings(self) -> None:
        """Open the Application Settings dialog directly to the Hotkeys page."""
        from shotx.ui.settings_dialog import ApplicationSettingsDialog

        # 3 is the index of the Hotkeys tab
        dialog = ApplicationSettingsDialog(self._app._settings_manager, start_page=3, parent=self)
        if dialog.exec():
            self._app.apply_hotkeys()

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

    def _on_open_history(self) -> None:
        """Open the History spreadsheet in a floating standalone window."""
        from shotx.ui.history import HistoryDialog
        # Open without parent so it's an independent top-level window
        # that doesn't always stack on top of the main window.
        self._history_dialog = HistoryDialog(self._app)
        self._history_dialog.show()
        self._history_dialog.raise_()
        self._history_dialog.activateWindow()

    def _on_image_history_refresh(self) -> None:
        """Refresh the embedded image history thumbnail grid."""
        self._image_history_widget._load_data(clear=True)

    def _on_upload_file(self) -> None:
        """Open a file dialog and upload the selected image."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select image to upload",
            str(Path(self._app.settings.capture.output_dir).expanduser()),
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)",
        )
        if path:
            from shotx.core.events import event_bus
            event_bus.upload_requested.emit(path)

    def _on_upload_clipboard(self) -> None:
        """Upload the current clipboard image."""
        import tempfile
        from pathlib import Path

        from PySide6.QtWidgets import QApplication, QMessageBox

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
        from shotx.core.events import event_bus
        event_bus.upload_requested.emit(str(tmp))

    def _on_shorten_url_clipboard(self) -> None:
        """Shorten any URL currently in the clipboard."""
        self._app.shorten_clipboard_url()

    def _on_about(self) -> None:
        """Show the redesigned About dialog."""
        ShotXAboutDialog.show_about(self)
