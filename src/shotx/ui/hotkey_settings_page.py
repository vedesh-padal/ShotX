"""Hotkey settings page for the main settings dialog."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QGroupBox,
    QKeySequenceEdit,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QApplication,
)
from PySide6.QtGui import QKeySequence
from shotx.config.settings import SettingsManager


class HotkeySettingsPage(QWidget):
    """UI for configuring global keyboard shortcuts."""

    def __init__(self, settings_manager: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings_manager = settings_manager
        
        # Keep references to edits for saving back later
        self._edits: dict[str, QKeySequenceEdit] = {}
        
        self._init_ui()
        self.load_settings()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        from shotx.core.platform import is_wayland
        _is_wayland = is_wayland()
        
        # --- Standard Hotkeys Group ---
        group_internal = QGroupBox("Internal App Keyboard Shortcuts")
        form = QFormLayout(group_internal)
        
        # Mappings: (settings_key, Label)
        mappings = [
            ("capture_fullscreen", "Capture Fullscreen:"),
            ("capture_region", "Capture Region:"),
            ("capture_window", "Capture Window:"),
            ("capture_ocr", "Extract Text (OCR):"),
            ("capture_color_picker", "Color Picker:"),
            ("capture_ruler", "Screen Ruler:"),
            ("capture_qr_scan", "Scan QR Code:"),
            ("pin_region", "Pin Region to Screen:"),
        ]
        
        for key, label in mappings:
            edit = QKeySequenceEdit()
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(lambda _, e=edit: e.clear())
            
            row_layout = QHBoxLayout()
            row_layout.addWidget(edit)
            row_layout.addWidget(clear_btn)
            
            form.addRow(label, row_layout)
            self._edits[key] = edit
            
        layout.addWidget(group_internal)
        
        # --- Wayland / Global Shortcuts Warning Banner ---
        banner = QFrame()
        banner.setObjectName("warningBanner")
        banner.setStyleSheet("""
            QFrame#warningBanner {
                background-color: #2b2b2b;
                border: 1px solid #ffcc00;
                border-radius: 6px;
                padding: 10px;
                margin-top: 10px;
            }
        """)
        banner_layout = QVBoxLayout(banner)
        
        warning_lbl = QLabel(
            "<b>⚠️ Notice: True Global Hotkeys on Wayland</b><br>"
            "Due to Wayland's strict security model, the app cannot capture keystrokes globally based on internal settings. "
            "For true global hotkeys across your entire system, "
            "please open your Desktop Environment's Settings (e.g., Ubuntu Settings -> Keyboard -> "
            "Custom Shortcuts) and map your desired keys to the following CLI commands:"
        )
        warning_lbl.setWordWrap(True)
        banner_layout.addWidget(warning_lbl)
        
        cli_commands = [
            ("Region / Window Capture", "shotx --capture-region"),
            ("Fullscreen Capture", "shotx --capture-fullscreen"),
            ("Color Picker", "shotx --color-picker"),
            ("Extract Text (OCR)", "shotx --ocr"),
            ("Screen Ruler", "shotx --ruler"),
        ]
        
        cmd_layout = QFormLayout()
        for cmd_label, cmd in cli_commands:
            row_lyt = QHBoxLayout()
            lbl_cmd = QLabel(f"<code>{cmd}</code>")
            lbl_cmd.setStyleSheet("background: #1e1e1e; padding: 4px; border-radius: 3px; font-family: monospace;")
            btn_copy = QPushButton("Copy")
            
            # Helper for visual feedback
            def make_copy_handler(text=cmd, btn=btn_copy):
                def handler():
                    from PySide6.QtCore import QTimer
                    QApplication.clipboard().setText(text)
                    btn.setText("Copied!")
                    QTimer.singleShot(1500, lambda: btn.setText("Copy"))
                return handler
                
            btn_copy.clicked.connect(make_copy_handler())
            
            row_lyt.addWidget(lbl_cmd, stretch=1)
            row_lyt.addWidget(btn_copy)
            cmd_layout.addRow(cmd_label + ":", row_lyt)
            
        banner_layout.addLayout(cmd_layout)
        layout.addWidget(banner)
        
        if _is_wayland:
            group_internal.setVisible(False)
            banner.setVisible(True)
        else:
            group_internal.setVisible(True)
            banner.setVisible(False)
            
        layout.addStretch()

    def load_settings(self) -> None:
        """Load hotkeys from settings into the UI."""
        s = self._settings_manager.settings.hotkeys
        
        for key, edit in self._edits.items():
            val = getattr(s, key, "")
            edit.setKeySequence(QKeySequence(val))

    def apply_settings(self) -> None:
        """Apply the inputs back to the settings manager.
        Note: The caller is responsible for actually calling _settings_manager.save()
        and live-reloading the app's HotkeyManager.
        """
        s = self._settings_manager.settings.hotkeys
        
        for key, edit in self._edits.items():
            # QKeySequence.toString() returns e.g. "Ctrl+Print"
            seq_str = edit.keySequence().toString()
            setattr(s, key, seq_str)
