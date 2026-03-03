from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QWidget,
    QLabel,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QPushButton,
    QFormLayout,
    QGroupBox,
)

from shotx.config.settings import SettingsManager


class TaskSettingsDialog(QDialog):
    """Configuration dialog matching ShareX's Task settings."""

    def __init__(self, settings_manager: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Task Settings - ShotX")
        self.setMinimumSize(600, 450)
        self._settings_manager = settings_manager

        self._init_ui()
        self._load_current_settings()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # -- Left Navigation --
        self._nav_list = QListWidget()
        self._nav_list.setFixedWidth(160)
        self._nav_list.addItems(
            [
                "General",
                "Notifications",
                "Image",
                "Capture",
                "→ Region capture",
                "→ Screen recorder",
                "Upload",
            ]
        )
        self._nav_list.currentRowChanged.connect(self._on_page_changed)
        layout.addWidget(self._nav_list)

        # -- Right Content Area --
        right_layout = QVBoxLayout()
        self._stack = QStackedWidget()

        # Build pages
        self._page_general = self._build_general_page()
        self._page_notifications = self._build_notifications_page()
        self._page_image = self._build_image_page()
        self._page_capture = self._build_capture_page()
        self._page_region = self._build_region_page()
        self._page_recorder = self._build_recorder_page()
        self._page_upload = self._build_upload_page()

        self._stack.addWidget(self._page_general)
        self._stack.addWidget(self._page_notifications)
        self._stack.addWidget(self._page_image)
        self._stack.addWidget(self._page_capture)
        self._stack.addWidget(self._page_region)
        self._stack.addWidget(self._page_recorder)
        self._stack.addWidget(self._page_upload)

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
        l.addWidget(QLabel("General task settings (Placeholder)"))
        l.addStretch()
        return w

    def _build_notifications_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        group = QGroupBox("Notifications")
        form = QFormLayout(group)
        
        self._chk_show_notif = QCheckBox("Show toast notification after capture")
        form.addRow("", self._chk_show_notif)
        
        self._chk_play_sound = QCheckBox("Play sound after capture")
        form.addRow("", self._chk_play_sound)
        
        l.addWidget(group)
        l.addStretch()
        return w

    def _build_image_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        group = QGroupBox("Image Formatting")
        form = QFormLayout(group)
        
        self._combo_format = QComboBox()
        self._combo_format.addItems(["png", "jpg", "jpeg", "webp"])
        form.addRow("Image format:", self._combo_format)
        
        self._spin_quality = QSpinBox()
        self._spin_quality.setRange(1, 100)
        form.addRow("JPEG/WebP Quality:", self._spin_quality)
        
        l.addWidget(group)
        l.addStretch()
        return w

    def _build_capture_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        group = QGroupBox("General Capture")
        form = QFormLayout(group)
        
        self._chk_cursor = QCheckBox("Show cursor in screenshots")
        form.addRow("", self._chk_cursor)
        
        self._spin_delay = QSpinBox()
        self._spin_delay.setSuffix(" sec")
        self._spin_delay.setRange(0, 60)
        form.addRow("Screenshot delay:", self._spin_delay)
        
        l.addWidget(group)
        l.addStretch()
        return w

    def _build_region_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("Region Capture options (Placeholder)"))
        l.addStretch()
        return w

    def _build_recorder_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        group = QGroupBox("Screen Recorder")
        form = QFormLayout(group)
        
        self._spin_fps = QSpinBox()
        self._spin_fps.setRange(1, 120)
        form.addRow("Video FPS:", self._spin_fps)
        
        self._chk_audio = QCheckBox("Capture Audio (PulseAudio/PipeWire)")
        form.addRow("", self._chk_audio)
        
        l.addWidget(group)
        l.addStretch()
        return w

    def _build_upload_page(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        
        group = QGroupBox("After Upload")
        form = QFormLayout(group)
        
        self._chk_copy_url = QCheckBox("Copy URL to clipboard")
        form.addRow("", self._chk_copy_url)
        
        self._chk_shorten_url = QCheckBox("Shorten URL")
        form.addRow("", self._chk_shorten_url)
        
        l.addWidget(group)
        l.addStretch()
        return w

    # -------------------------------------------------------------------------
    # Data Binding
    # -------------------------------------------------------------------------

    def _load_current_settings(self) -> None:
        s = self._settings_manager.settings
        
        # Notifications
        self._chk_show_notif.setChecked(s.capture.show_notification)
        self._chk_play_sound.setChecked(s.capture.play_sound)
        
        # Image
        idx = self._combo_format.findText(s.capture.image_format.lower())
        if idx >= 0:
            self._combo_format.setCurrentIndex(idx)
        self._spin_quality.setValue(s.capture.jpeg_quality)
        
        # Capture
        self._chk_cursor.setChecked(s.capture.show_cursor)
        self._spin_delay.setValue(s.capture.screenshot_delay)
        
        # Recorder
        self._spin_fps.setValue(s.capture.video_fps)
        self._chk_audio.setChecked(s.capture.capture_audio)
        
        # Upload
        self._chk_copy_url.setChecked(s.upload.copy_url_to_clipboard)
        self._chk_shorten_url.setChecked(s.upload.shortener.enabled)

    def accept(self) -> None:
        s = self._settings_manager.settings
        
        # Notifications
        s.capture.show_notification = self._chk_show_notif.isChecked()
        s.capture.play_sound = self._chk_play_sound.isChecked()
        
        # Image
        s.capture.image_format = self._combo_format.currentText()
        s.capture.jpeg_quality = self._spin_quality.value()
        
        # Capture
        s.capture.show_cursor = self._chk_cursor.isChecked()
        s.capture.screenshot_delay = self._spin_delay.value()
        
        # Recorder
        s.capture.video_fps = self._spin_fps.value()
        s.capture.capture_audio = self._chk_audio.isChecked()
        
        # Upload
        s.upload.copy_url_to_clipboard = self._chk_copy_url.isChecked()
        s.upload.shortener.enabled = self._chk_shorten_url.isChecked()
        
        self._settings_manager.save()
        super().accept()

    def _on_page_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
