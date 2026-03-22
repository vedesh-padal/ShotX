"""ShotX Welcome Dialog — First-Run Integration.

A modern, frosty-glass dialog that appears on the first launch to help
users integrate ShotX with their desktop environment.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shotx.ui.theme import Theme

if TYPE_CHECKING:
    pass


class ShotXWelcomeDialog(QDialog):
    """A polite invitation to integrate ShotX with the system on first run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to ShotX")
        self.setFixedSize(500, 280)
        self.setStyleSheet(Theme.get_glass_dialog_qss())

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Content Container
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(30, 30, 30, 24)
        content_layout.setSpacing(20)

        # --- Top Section (Logo + Heading) ---
        header_hbox = QHBoxLayout()
        header_hbox.setSpacing(20)

        # Logo
        logo_label = QLabel()
        try:
            logo_path = pkg_resources.files("shotx.assets").joinpath("shotx.png")
            pixmap = QPixmap(str(logo_path))
            logo_label.setPixmap(pixmap.scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        except Exception:
            logo_label.setText("📷")
            logo_label.setStyleSheet("font-size: 32px;")

        header_hbox.addWidget(logo_label)

        # Heading
        heading_vbox = QVBoxLayout()
        heading_vbox.setSpacing(4)

        welcome_title = QLabel(f"<b style='font-size: 22px; color: {Theme.ACCENT_PURPLE};'>Welcome to ShotX!</b>")
        tagline = QLabel(f"<span style='color: {Theme.TEXT_SECONDARY};'>Let's set up your experience.</span>")

        heading_vbox.addWidget(welcome_title)
        heading_vbox.addWidget(tagline)
        heading_vbox.addStretch()

        header_hbox.addLayout(heading_vbox)
        header_hbox.addStretch()
        content_layout.addLayout(header_hbox)

        # --- Body Section ---
        body_label = QLabel(
            "Would you like to integrate ShotX with your desktop? "
            "This will add it to your <b>Application Menu</b> and set it to "
            "<b>Start on Login</b> for a seamless experience."
        )
        body_label.setWordWrap(True)
        body_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; line-height: 1.5;")
        content_layout.addWidget(body_label)

        content_layout.addStretch()

        # --- Action Section ---
        actions_hbox = QHBoxLayout()
        actions_hbox.setSpacing(12)

        btn_skip = QPushButton("Maybe Later")
        btn_skip.setFixedWidth(120)
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.clicked.connect(self._on_maybe_later)
        # Style as secondary/hollow
        btn_skip.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Theme.TEXT_MUTED};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.05);
                border-color: {Theme.TEXT_SECONDARY};
            }}
        """)

        btn_integrate = QPushButton("Integrate Now")
        btn_integrate.setFixedWidth(160)
        btn_integrate.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_integrate.clicked.connect(self.accept)

        actions_hbox.addStretch()
        actions_hbox.addWidget(btn_skip)
        actions_hbox.addWidget(btn_integrate)

        content_layout.addLayout(actions_hbox)
        layout.addWidget(content_wrapper)

    @classmethod
    def show_welcome(cls, parent: QWidget | None = None) -> int:
        """Show the dialog and return the result code.

        Codes:
            1 (Accepted): Integrate Now
            2: Maybe Later
            0 (Rejected/Closed): Dismissed (will show again)
        """
        dlg = cls(parent)
        return dlg.exec()

    def _on_maybe_later(self) -> None:
        """User explicitly clicked 'Maybe Later'."""
        self.done(2)
