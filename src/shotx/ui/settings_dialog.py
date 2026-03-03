from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QWidget,
    QLabel,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QFormLayout,
    QGroupBox,
)
from PySide6.QtCore import Qt

from shotx.config.settings import SettingsManager


class ApplicationSettingsDialog(QDialog):
    """Deep configuration dialog matching ShareX's Application settings."""

    def __init__(self, settings_manager: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Application Settings - ShotX")
        self.setMinimumSize(700, 500)
        self._settings_manager = settings_manager

        self._init_ui()
        self._load_current_settings()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # -- Left Navigation --
        self._nav_list = QListWidget()
        self._nav_list.setFixedWidth(160)
        self._nav_list.addItems(["General", "Paths", "Upload", "History", "Advanced"])
        self._nav_list.currentRowChanged.connect(self._on_page_changed)
        layout.addWidget(self._nav_list)

        # -- Right Content Area --
        right_layout = QVBoxLayout()
        self._stack = QStackedWidget()

        # Build pages
        self._page_general = self._build_general_page()
        self._page_paths = self._build_paths_page()
        self._page_upload = self._build_upload_page()
        self._page_history = self._build_history_page()
        self._page_advanced = self._build_advanced_page()

        self._stack.addWidget(self._page_general)
        self._stack.addWidget(self._page_paths)
        self._stack.addWidget(self._page_upload)
        self._stack.addWidget(self._page_history)
        self._stack.addWidget(self._page_advanced)

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

        self._nav_list.setCurrentRow(0)

    # -------------------------------------------------------------------------
    # Page Builders
    # -------------------------------------------------------------------------

    def _build_general_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        
        # System Tray logic
        group_tray = QGroupBox("System Tray")
        gl_tray = QVBoxLayout(group_tray)
        self._chk_show_tray = QCheckBox("Show tray icon")
        gl_tray.addWidget(self._chk_show_tray)
        l.addWidget(group_tray)
        
        # Capture Config behavior
        group_cap = QGroupBox("Capture Settings")
        form_cap = QFormLayout(group_cap)
        
        self._check_auto_detect = QCheckBox("Auto-detect UI elements (windows, buttons) across system")
        form_cap.addRow("", self._check_auto_detect)
        
        self._combo_after_cap_action = QComboBox()
        self._combo_after_cap_action.addItems(["Go to Editor", "Save Directly"])
        form_cap.addRow("Default flow upon region capture:", self._combo_after_cap_action)
        
        l.addWidget(group_cap)
        l.addStretch()
        return w

    def _build_paths_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        
        group = QGroupBox("Directories & Output Patterns")
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
        self._edit_filename.setToolTip("Available variables: {date}, {time}, {y}, {m}, {d}, {h}, {min}, {s}, {rnd}")
        form.addRow("Filename pattern:", self._edit_filename)
        
        l.addWidget(group)
        l.addStretch()
        return w

    def _build_upload_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        
        group = QGroupBox("Upload Engine")
        form = QFormLayout(group)
        
        self._chk_upload_enabled = QCheckBox("Enable background uploading engine")
        form.addRow("", self._chk_upload_enabled)
        
        self._combo_default_uploader = QComboBox()
        self._combo_default_uploader.addItems(["imgur", "tmpfiles", "imgbb", "s3", "ftp", "sftp", "custom"])
        form.addRow("Default Image Uploader:", self._combo_default_uploader)
        
        l.addWidget(group)
        l.addStretch()
        return w

    def _build_history_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        l.addWidget(QLabel("History retention functionality goes here."))
        l.addStretch()
        return w

    def _build_advanced_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        l.addWidget(QLabel("Advanced/developer functionality goes here."))
        l.addStretch()
        return w

    # -------------------------------------------------------------------------
    # Data Binding
    # -------------------------------------------------------------------------

    def _load_current_settings(self) -> None:
        """Populate UI fields from the current settings dict."""
        s = self._settings_manager.settings
        
        # General Page
        self._chk_show_tray.setChecked(True)  # Placeholder: Actually needs matching in AppSettings later
        self._check_auto_detect.setChecked(s.capture.auto_detect_regions)
        action_idx = 0 if s.capture.after_capture_action == "edit" else 1
        self._combo_after_cap_action.setCurrentIndex(action_idx)
        
        # Paths Page
        self._edit_out_dir.setText(s.capture.output_dir)
        self._edit_filename.setText(s.capture.filename_pattern)
        
        # Upload Page
        self._chk_upload_enabled.setChecked(s.upload.enabled)
        idx = self._combo_default_uploader.findText(s.upload.default_uploader)
        if idx >= 0:
            self._combo_default_uploader.setCurrentIndex(idx)

    def accept(self) -> None:
        """Save settings and close dialog."""
        s = self._settings_manager.settings
        
        # General Page
        s.capture.auto_detect_regions = self._check_auto_detect.isChecked()
        s.capture.after_capture_action = "edit" if self._combo_after_cap_action.currentIndex() == 0 else "save"
        
        # Paths Page
        s.capture.output_dir = self._edit_out_dir.text()
        s.capture.filename_pattern = self._edit_filename.text()
        
        # Upload Page
        s.upload.enabled = self._chk_upload_enabled.isChecked()
        s.upload.default_uploader = self._combo_default_uploader.currentText()
        
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
