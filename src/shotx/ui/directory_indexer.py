"""UI dialog for the Directory Indexer tool."""

from __future__ import annotations
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QFileDialog, QFrame, QApplication
)

from shotx.tools.indexer import generate_directory_index

class DirectoryIndexerDialog(QDialog):
    """Modern dialog for generating directory HTML indexes."""

    def __init__(self, parent=None, initial_dir: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("ShotX — Directory Indexer")
        
        # Disable Maximize button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        
        # Set dimension constraints (allow limited resizing up to +50%)
        self.setMinimumSize(550, 250)
        self.setMaximumSize(825, 450)
        
        self.last_generated_path: Path | None = None
        
        # Unified Nord Theme (Consistent across Light/Dark systems)
        self._apply_nord_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 1. Directory Selection Section
        input_frame = QFrame()
        input_frame.setObjectName("GroupFrame")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 15, 15, 15)
        input_layout.setSpacing(10)
        
        title_label = QLabel("Select Directory to Index:")
        title_label.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        input_layout.addWidget(title_label)
        
        path_row = QHBoxLayout()
        self.path_input = QLineEdit(initial_dir)
        self.path_input.setPlaceholderText("e.g., /home/user/Pictures/Screenshots")
        path_row.addWidget(self.path_input)

        self.btn_browse = QPushButton("📁 Browse")
        self.btn_browse.setObjectName("ActionBtn")
        self.btn_browse.clicked.connect(self._on_browse)
        path_row.addWidget(self.btn_browse)
        
        input_layout.addLayout(path_row)
        layout.addWidget(input_frame)

        # 2. Action Section
        self.btn_generate = QPushButton("🚀 Generate Index.html")
        self.btn_generate.setObjectName("PrimaryBtn")
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setFont(QFont("Inter", 11, QFont.Weight.DemiBold))
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_generate)
        
        # 3. Status/Result Section
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        
        self.btn_open = QPushButton("🌐 Open in Browser")
        self.btn_open.setObjectName("ActionBtn")
        self.btn_open.clicked.connect(self._on_open_browser)
        self.btn_open.hide()
        layout.addWidget(self.btn_open)

    def _apply_nord_theme(self) -> None:
        """Applies a standalone Nord-inspired stylesheet."""
        self.setStyleSheet("""
            QDialog { 
                background-color: #2e3440; 
            }
            #GroupFrame { 
                background-color: #3b4252; 
                border: 1px solid #434c5e; 
                border-radius: 8px; 
            }
            QLabel { 
                color: #eceff4; 
                font-weight: 500; 
            }
            QLineEdit { 
                background-color: #242933; 
                color: #eceff4; 
                border: 1px solid #434c5e; 
                border-radius: 4px; 
                padding: 6px; 
                font-family: 'Monospace', 'Cousine';
            }
            QLineEdit:focus {
                border: 1px solid #88c0d0;
                background-color: #2e3440;
            }
            QPushButton { 
                background-color: #434c5e; 
                color: #eceff4; 
                border: 1px solid #4c566a; 
                padding: 6px 12px; 
                border-radius: 4px; 
            }
            QPushButton:hover { 
                background-color: #4c566a; 
            }
            #ActionBtn { 
                background-color: #434c5e; 
                color: #eceff4; 
                font-weight: bold; 
                padding: 8px 16px; 
            }
            #ActionBtn:hover { 
                background-color: #4c566a; 
            }
            #PrimaryBtn { 
                background-color: #5e81ac; 
                color: #eceff4; 
                font-weight: bold; 
                border: none;
                border-radius: 6px;
            }
            #PrimaryBtn:hover { 
                background-color: #81a1c1; 
            }
            #PrimaryBtn:pressed { 
                background-color: #4c566a; 
            }
            #SuccessLabel {
                color: #a3be8c;
                font-weight: bold;
            }
            #ErrorLabel {
                color: #bf616a;
                font-weight: bold;
            }
        """)

    def _on_browse(self) -> None:
        start_dir = self.path_input.text() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory", start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            self.path_input.setText(directory)
            self._reset_status()

    def _reset_status(self) -> None:
        self.status_label.hide()
        self.btn_open.hide()
        self.last_generated_path = None

    def _on_generate(self) -> None:
        self._reset_status()
        
        target_dir = self.path_input.text().strip()
        if not target_dir:
            self._show_error("Please select a directory first.")
            return
            
        # Fix path expansion so ~/ works correctly
        expanded_target = str(Path(target_dir).expanduser().resolve())
            
        try:
            output_path = generate_directory_index(expanded_target)
            self.last_generated_path = output_path
            
            # Format nicely. If the user typed ~, don't blow it up to the full path 
            # in the success label just for display, keep it clean.
            self.status_label.setText(f"✅ Successfully created:\n{output_path}")
            self.status_label.setObjectName("SuccessLabel")
            
            # Force stylesheet refresh for the dynamic objectName change
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
            
            self.status_label.show()
            self.btn_open.show()
            
        except Exception as e:
            self._show_error(f"Failed to generate index: {e}")

    def _show_error(self, message: str) -> None:
        self.status_label.setText(f"❌\n{message}")
        self.status_label.setObjectName("ErrorLabel")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.show()
        
    def _on_open_browser(self) -> None:
        if self.last_generated_path and self.last_generated_path.exists():
            webbrowser.open(self.last_generated_path.as_uri())
