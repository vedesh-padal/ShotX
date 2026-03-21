"""UI dialog for calculating and displaying file/text hashes."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from shotx.tools.hash_tool import calculate_file_hashes, calculate_hashes
from shotx.ui.theme import Theme


class HashDialog(QDialog):
    """Modern dialog for calculating hashes with a unified Nord-inspired theme."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ShotX — Hash Checker")

        # On GNOME/Wayland, the only native way to remove the Maximize
        # button is to make the dialog a fixed size.
        self.setFixedSize(650, 400)

        # Unified Theme
        self._apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 1. Input Section
        input_frame = QFrame()
        input_frame.setObjectName("GroupFrame")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_file = QPushButton("📁 Open File")
        self.btn_file.setObjectName("ActionBtn")
        self.btn_file.clicked.connect(self._on_open_file)

        self.btn_clipboard = QPushButton("📋 Paste from Clipboard")
        self.btn_clipboard.setObjectName("ActionBtn")
        self.btn_clipboard.clicked.connect(self._on_paste_clipboard)

        input_layout.addWidget(self.btn_file)
        input_layout.addWidget(self.btn_clipboard)
        layout.addWidget(input_frame)

        # 2. Results Section (Form Layout)
        results_frame = QFrame()
        results_frame.setObjectName("GroupFrame")
        results_vbox = QVBoxLayout(results_frame)

        self.form_layout = QFormLayout()
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form_layout.setSpacing(10)

        self.hash_lines: dict[str, QLineEdit] = {}
        for algo in ["MD5", "SHA1", "SHA256"]:
            row = QHBoxLayout()

            line = QLineEdit()
            line.setReadOnly(True)
            line.setPlaceholderText(f"Calculate {algo}...")
            self.hash_lines[algo] = line

            btn_copy = QPushButton("Copy")
            btn_copy.setFixedWidth(90)
            btn_copy.clicked.connect(lambda checked=False, a=algo, b=btn_copy: self._on_copy_hash(a, b))

            row.addWidget(line)
            row.addWidget(btn_copy)

            label = QLabel(f"{algo}:")
            self.form_layout.addRow(label, row)

        results_vbox.addLayout(self.form_layout)
        layout.addWidget(results_frame)

        # 3. Verification Section
        verify_frame = QFrame()
        verify_frame.setObjectName("GroupFrame")
        verify_layout = QVBoxLayout(verify_frame)

        v_header = QLabel("Verify against known hash:")
        verify_layout.addWidget(v_header)

        self.verify_input = QLineEdit()
        self.verify_input.setPlaceholderText("Paste hash here to verify...")
        self.verify_input.textChanged.connect(self._on_verify_changed)
        verify_layout.addWidget(self.verify_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(30)
        verify_layout.addWidget(self.status_label)

        layout.addWidget(verify_frame)

    def _apply_theme(self) -> None:
        """Apply the global ShotX theme."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BASE_DARK};
            }}
            QFrame#GroupFrame {{
                background-color: {Theme.BASE_LIGHTER};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
                font-weight: 500;
            }}
            QLineEdit {{
                background-color: {Theme.BASE_DARK};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px;
                font-family: 'Monospace', 'Cousine';
            }}
            QPushButton {{
                background-color: {Theme.BASE_LIGHTER};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            QPushButton#ActionBtn {{
                background-color: {Theme.ACCENT_PURPLE};
                color: #ffffff;
                font-weight: bold;
                padding: 10px;
                border: none;
            }}
            QPushButton#ActionBtn:hover {{
                background-color: {Theme.ACCENT_PURPLE};
                opacity: 0.9;
            }}
        """)
        self._success_color = "#a3be8c" # Keep soft green for success
        self._error_color = "#bf616a"   # Keep soft red for error

    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Hash")
        if file_path:
            try:
                hashes = calculate_file_hashes(file_path)
                self._display_hashes(hashes)
            except Exception as e:
                self.status_label.setText(f"Error: {e}")
                self.status_label.setStyleSheet(f"color: {self._error_color};")

    def _on_paste_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            hashes = calculate_hashes(text)
            self._display_hashes(hashes)
        else:
            self.status_label.setText("No text in clipboard!")
            self.status_label.setStyleSheet(f"color: {self._error_color};")

    def _display_hashes(self, hashes: dict[str, str]) -> None:
        for algo, val in hashes.items():
            self.hash_lines[algo].setText(val)
        self.status_label.setText("Hashes calculated successfully.")
        self.status_label.setStyleSheet(f"color: {self._success_color}; font-weight: bold;")
        self._on_verify_changed()

    def _on_copy_hash(self, algo: str, button: QPushButton) -> None:
        val = self.hash_lines[algo].text()
        if val:
            QApplication.clipboard().setText(val)
            # Visual feedback
            button.setText("Copied!")
            button.setStyleSheet(f"background-color: {self._success_color}; color: #2e3440; border: none; font-weight: bold;")
            QTimer.singleShot(1000, lambda: self._reset_button(button))

    def _reset_button(self, button: QPushButton) -> None:
        button.setText("Copy")
        button.setStyleSheet("")

    def _on_verify_changed(self) -> None:
        verify_val = self.verify_input.text().strip().lower()
        if not verify_val:
            self.status_label.setText("")
            return

        found_match = False
        for line in self.hash_lines.values():
            if line.text().lower() == verify_val:
                found_match = True
                break

        if found_match:
            self.status_label.setText("✅ Match Found!")
            self.status_label.setStyleSheet(f"color: {self._success_color}; font-weight: bold;")
        else:
            self.status_label.setText("❌ No Match")
            self.status_label.setStyleSheet(f"color: {self._error_color}; font-weight: bold;")
