"""UI dialog for calculating and displaying file/text hashes."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QFileDialog, QPlainTextEdit, QFrame
)

from shotx.tools.hash_tool import calculate_hashes, calculate_file_hashes

class HashDialog(QDialog):
    """Dialog for calculating MD5, SHA1, SHA256 hashes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ShotX — Hash Checker")
        self.setMinimumWidth(500)
        
        # UI Setup
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
            }
            QLineEdit, QPlainTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton#primary {
                background-color: #007bff;
            }
            QPushButton#primary:hover {
                background-color: #0056b3;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 1. Input Selection
        btn_layout = QHBoxLayout()
        self.btn_file = QPushButton("📁 Open File")
        self.btn_file.clicked.connect(self._on_open_file)
        
        self.btn_clipboard = QPushButton("📋 Paste from Clipboard")
        self.btn_clipboard.clicked.connect(self._on_paste_clipboard)
        
        btn_layout.addWidget(self.btn_file)
        btn_layout.addWidget(self.btn_clipboard)
        layout.addLayout(btn_layout)

        # 2. Results Section
        self.results_frame = QFrame()
        self.results_layout = QVBoxLayout(self.results_frame)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        
        self.hash_lines: dict[str, QLineEdit] = {}
        for algo in ["MD5", "SHA1", "SHA256"]:
            row = QHBoxLayout()
            label = QLabel(f"{algo}:")
            label.setFixedWidth(60)
            
            line = QLineEdit()
            line.setReadOnly(True)
            self.hash_lines[algo] = line
            
            btn_copy = QPushButton("Copy")
            btn_copy.setFixedWidth(90)
            btn_copy.clicked.connect(lambda checked=False, a=algo, b=btn_copy: self._on_copy_hash(a, b))
            
            row.addWidget(label)
            row.addWidget(line)
            row.addWidget(btn_copy)
            self.results_layout.addLayout(row)
        
        layout.addWidget(self.results_frame)

        # 3. Verification Section
        v_label = QLabel("Verify against hash:")
        layout.addWidget(v_label)
        
        self.verify_input = QLineEdit()
        self.verify_input.setPlaceholderText("Paste hash here to verify...")
        self.verify_input.textChanged.connect(self._on_verify_changed)
        layout.addWidget(self.verify_input)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Hash")
        if file_path:
            try:
                hashes = calculate_file_hashes(file_path)
                self._display_hashes(hashes)
            except Exception as e:
                self.status_label.setText(f"Error: {e}")
                self.status_label.setStyleSheet("color: #ff4444;")

    def _on_paste_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            hashes = calculate_hashes(text)
            self._display_hashes(hashes)
        else:
            self.status_label.setText("No text in clipboard!")
            self.status_label.setStyleSheet("color: #ffaa00;")

    def _display_hashes(self, hashes: dict[str, str]) -> None:
        for algo, val in hashes.items():
            self.hash_lines[algo].setText(val)
        self.status_label.setText("Hashes calculated successfully.")
        self.status_label.setStyleSheet("color: #00ff00;")
        self._on_verify_changed()

    def _on_copy_hash(self, algo: str, button: QPushButton) -> None:
        from PySide6.QtWidgets import QApplication
        val = self.hash_lines[algo].text()
        if val:
            QApplication.clipboard().setText(val)
            # Visual feedback
            button.setText("Copied!")
            button.setStyleSheet("background-color: #28a745; color: white;")
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
            self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        else:
            self.status_label.setText("❌ No Match")
            self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
