from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shotx.config.settings import SettingsManager
from shotx.ui.theme import Theme


class ApplicationSettingsDialog(QDialog):
    """Deep configuration dialog matching ShareX's Application settings."""

    def __init__(self, settings_manager: SettingsManager, start_page: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Application Settings - ShotX")
        self.setMinimumSize(700, 500)
        self._settings_manager = settings_manager
        self._start_page = start_page

        from shotx.ui.styles import SETTINGS_QSS
        self.setStyleSheet(SETTINGS_QSS)

        self._init_ui()
        self._load_current_settings()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # -- Left Navigation --
        self._nav_list = QListWidget()
        self._nav_list.setFixedWidth(160)
        self._nav_list.addItems(["General", "Paths", "Upload", "Hotkeys"])
        self._nav_list.currentRowChanged.connect(self._on_page_changed)
        layout.addWidget(self._nav_list)

        # -- Right Content Area --
        right_layout = QVBoxLayout()
        self._stack = QStackedWidget()

        # Build pages
        self._page_general = self._build_general_page()
        self._page_paths = self._build_paths_page()
        self._page_upload = self._build_upload_page()

        from shotx.ui.hotkey_settings_page import HotkeySettingsPage
        self._page_hotkeys = HotkeySettingsPage(self._settings_manager)

        self._stack.addWidget(self._page_general)
        self._stack.addWidget(self._page_paths)
        self._stack.addWidget(self._page_upload)
        self._stack.addWidget(self._page_hotkeys)

        right_layout.addWidget(self._stack)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_ok = QPushButton("OK")
        self._btn_ok.clicked.connect(self.accept)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self._btn_ok)
        btn_layout.addWidget(self._btn_cancel)

        right_layout.addLayout(btn_layout)
        layout.addLayout(right_layout, stretch=1)

        self._nav_list.setCurrentRow(self._start_page)

    # -------------------------------------------------------------------------
    # Page Builders
    # -------------------------------------------------------------------------

    def _build_general_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        # System Tray logic
        group_tray = QGroupBox("System Tray")
        gl_tray = QVBoxLayout(group_tray)
        self._chk_show_tray = QCheckBox("Show tray icon")
        gl_tray.addWidget(self._chk_show_tray)

        self._chk_autostart = QCheckBox("Start ShotX on login")
        gl_tray.addWidget(self._chk_autostart)

        layout.addWidget(group_tray)

        # Capture Config behavior
        group_cap = QGroupBox("Capture Settings")
        form_cap = QFormLayout(group_cap)

        self._check_auto_detect = QCheckBox("Auto-detect UI elements (windows, buttons) across system")
        form_cap.addRow("", self._check_auto_detect)

        self._combo_after_cap_action = QComboBox()
        self._combo_after_cap_action.addItems(["Go to Editor", "Save Directly"])
        form_cap.addRow("Default flow upon region capture:", self._combo_after_cap_action)

        layout.addWidget(group_cap)
        layout.addStretch()
        return w

    def _build_paths_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Directories and Output Patterns")
        form = QFormLayout(group)

        # Output directory row
        dir_layout = QHBoxLayout()
        self._edit_out_dir = QLineEdit()
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._on_browse_output_dir)
        dir_layout.addWidget(self._edit_out_dir)
        dir_layout.addWidget(btn_browse)
        form.addRow("Screenshots folder:", dir_layout)

        # Filename pattern
        self._edit_filename = QLineEdit()
        self._edit_filename.setPlaceholderText("ShotX_{date}_{time}")

        help_text = QLabel(
            "<small>Available variables: {date}, {time}, {y}, {m}, {d}, {h}, {min}, {s}, {rnd}</small>"
        )
        help_text.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")

        self._label_preview = QLabel("Preview: ")
        self._label_preview.setStyleSheet(f"font-style: italic; color: {Theme.ACCENT_PURPLE};")

        self._edit_filename.textChanged.connect(self._update_filename_preview)

        form.addRow("Filename pattern:", self._edit_filename)
        form.addRow("", help_text)
        form.addRow("", self._label_preview)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _build_upload_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Upload Engine")
        form = QFormLayout(group)

        self._chk_upload_enabled = QCheckBox("Enable background uploading engine")
        form.addRow("", self._chk_upload_enabled)

        self._combo_default_uploader = QComboBox()
        self._combo_default_uploader.addItems(["imgur", "tmpfiles", "imgbb", "s3", "ftp", "sftp", "custom"])
        form.addRow("Default Image Uploader:", self._combo_default_uploader)

        layout.addWidget(group)
        layout.addStretch()
        return w



    # -------------------------------------------------------------------------
    # Data Binding
    # -------------------------------------------------------------------------

    def _load_current_settings(self) -> None:
        """Populate UI fields from the current settings dict."""
        s = self._settings_manager.settings

        # General Page
        self._chk_show_tray.setChecked(True)  # Placeholder: Actually needs matching in AppSettings later

        from shotx.core.desktop import is_autostart_enabled
        self._chk_autostart.setChecked(is_autostart_enabled())

        self._check_auto_detect.setChecked(s.capture.auto_detect_regions)
        action_idx = 0 if s.capture.after_capture_action == "edit" else 1
        self._combo_after_cap_action.setCurrentIndex(action_idx)

        # Paths Page
        self._edit_out_dir.setText(s.capture.output_dir)
        self._edit_filename.setText(s.capture.filename_pattern)
        self._update_filename_preview(s.capture.filename_pattern)

        # Upload Page
        self._chk_upload_enabled.setChecked(s.workflow.upload_image)
        uploader = s.upload.default_uploader.lower()
        for i in range(self._combo_default_uploader.count()):
            if self._combo_default_uploader.itemText(i).lower() == uploader:
                self._combo_default_uploader.setCurrentIndex(i)
                break

    def accept(self) -> None:
        """Save settings and close dialog."""
        from PySide6.QtWidgets import QMessageBox

        s = self._settings_manager.settings

        # Validation
        pattern = self._edit_filename.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Validation Error", "Filename pattern cannot be empty.")
            return

        try:
            self._render_preview(pattern)
        except Exception:
            QMessageBox.warning(self, "Validation Error", "Invalid variable used in filename pattern.")
            return

        # General Page
        s.capture.auto_detect_regions = self._check_auto_detect.isChecked()
        s.capture.after_capture_action = "edit" if self._combo_after_cap_action.currentIndex() == 0 else "save"

        from shotx.core.desktop import install_autostart, is_autostart_enabled, remove_autostart
        currently_enabled = is_autostart_enabled()
        should_enable = self._chk_autostart.isChecked()
        if should_enable and not currently_enabled:
            install_autostart()
        elif not should_enable and currently_enabled:
            remove_autostart()

        # Paths Page
        s.capture.output_dir = self._edit_out_dir.text()
        s.capture.filename_pattern = pattern

        # Upload Page
        s.workflow.upload_image = self._chk_upload_enabled.isChecked()
        s.upload.default_uploader = self._combo_default_uploader.currentText().lower()

        # Hotkeys Page (delegates to its own widget)
        self._page_hotkeys.apply_settings()

        self._settings_manager.save()
        super().accept()

    # -------------------------------------------------------------------------
    # Interactions
    # -------------------------------------------------------------------------

    def _on_page_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _on_browse_output_dir(self) -> None:
        start_dir = self._edit_out_dir.text() or str(Path.home())
        new_dir = QFileDialog.getExistingDirectory(self, "Select Screenshots Folder", start_dir)
        if new_dir:
            self._edit_out_dir.setText(new_dir)

    def _render_preview(self, pattern: str) -> str:
        """Helper to test a pattern."""
        import datetime
        import random
        now = datetime.datetime.now()
        vars_dict = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H-%M-%S"),
            "y": now.strftime("%Y"),
            "m": now.strftime("%m"),
            "d": now.strftime("%d"),
            "h": now.strftime("%H"),
            "min": now.strftime("%M"),
            "s": now.strftime("%S"),
            "rnd": f"{random.randint(0, 9999):04d}",
        }
        return pattern.format(**vars_dict)

    def _update_filename_preview(self, text: str) -> None:
        try:
            preview = self._render_preview(text)
            self._label_preview.setText(f"Preview: {preview}.png")
            self._label_preview.setStyleSheet(f"font-style: italic; color: {Theme.ACCENT_PURPLE};")
        except KeyError as e:
            self._label_preview.setText(f"Invalid variable: {e}")
            self._label_preview.setStyleSheet("color: red;")
        except ValueError:
            self._label_preview.setText("Invalid pattern formatting")
            self._label_preview.setStyleSheet("color: red;")
