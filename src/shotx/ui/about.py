"""ShotX About Dialog — The Branded Hub.

A modern, glassmorphism-inspired dialog that provides app information,
system status, and useful links.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shotx import __version__
from shotx.ui.theme import Theme

if TYPE_CHECKING:
    pass


class ShotXAboutDialog(QDialog):
    """Refined About dialog with a branded, modern look."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About ShotX")
        self.setFixedSize(520, 340)
        self.setStyleSheet(Theme.get_glass_dialog_qss())

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Content Container (The Glass Layer)
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(24, 24, 24, 16)
        content_layout.setSpacing(20)

        # --- Header Section (Logo + Title) ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)

        # Logo
        logo_label = QLabel()
        try:
            logo_path = pkg_resources.files("shotx.assets").joinpath("shotx.png")
            pixmap = QPixmap(str(logo_path))
            logo_label.setPixmap(
                pixmap.scaled(
                    80,
                    80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except Exception:
            logo_label.setText("📷")
            logo_label.setStyleSheet("font-size: 40px;")

        header_layout.addWidget(logo_label)

        # Title & Version
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)

        app_title = QLabel(f"<b style='font-size: 26px; color: {Theme.ACCENT_PURPLE};'>ShotX</b>")
        version_label = QLabel(
            f"<span style='color: {Theme.TEXT_SECONDARY};'>Version {__version__}</span>"
        )
        tagline = QLabel(
            f"<i style='color: {Theme.TEXT_MUTED};'>Modern Screen Capture for Linux</i>"
        )

        title_vbox.addWidget(app_title)
        title_vbox.addWidget(version_label)
        title_vbox.addWidget(tagline)
        title_vbox.addStretch()

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)

        # --- Details Section (Description + Credits + Status) ---
        details_layout = QVBoxLayout()
        details_layout.setSpacing(10)

        # Description
        desc_label = QLabel(
            "ShotX is a powerful, open-source screen capture and productivity suite "
            "designed for the modern Linux desktop. Inspired by ShareX, it brings "
            "instant capturing, editing, and uploading to your fingertips."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; line-height: 1.4;")
        details_layout.addWidget(desc_label)

        # Developer Info
        dev_label = QLabel(
            f"<b>Developed by:</b> <span style='color: {Theme.TEXT_PRIMARY};'>Vedesh Padal</span>"
        )
        details_layout.addWidget(dev_label)

        # System Status & Links
        status_hbox = QHBoxLayout()
        platform = QApplication.platformName()
        sys_name = "Wayland" if "wayland" in platform.lower() else "X11"
        status_label = QLabel(
            f"<b>System: </b> <span style='color: {Theme.ACCENT_PURPLE};'>{sys_name}</span>"
        )
        status_hbox.addWidget(status_label)
        status_hbox.addStretch()
        details_layout.addLayout(status_hbox)

        # Dynamic Links
        links_layout = QHBoxLayout()
        links_layout.setSpacing(16)
        links_data = [
            ("🌐 Website", "https://shotx.vedeshpadal.me"),
            ("🐙 GitHub", "https://github.com/vedesh-padal/ShotX"),
            ("📜 License", "https://github.com/vedesh-padal/ShotX?tab=GPL-3.0-1-ov-file#readme"),
        ]

        for text, url in links_data:
            link_label = QLabel(
                f"<a href='{url}' style='color: {Theme.ACCENT_PURPLE}; text-decoration: none;'>{text}</a>"
            )
            link_label.setOpenExternalLinks(True)
            link_label.setCursor(Qt.CursorShape.PointingHandCursor)
            links_layout.addWidget(link_label)

        links_layout.addStretch()
        details_layout.addLayout(links_layout)

        content_layout.addLayout(details_layout)
        content_layout.addStretch()

        # --- Footer Section (Buttons) ---
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)

        btn_docs = QPushButton("Visit Docs")
        btn_docs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_docs.clicked.connect(lambda: QDesktopServices.openUrl("https://shotx.vedeshpadal.me"))

        btn_ok = QPushButton("Close")
        btn_ok.setFixedWidth(100)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.accept)
        # Style the 'Close' button differently (hollow or secondary)
        btn_ok.setStyleSheet(f"""
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

        footer_layout.addStretch()
        footer_layout.addWidget(btn_docs)
        footer_layout.addWidget(btn_ok)

        content_layout.addLayout(footer_layout)
        layout.addWidget(content_wrapper)

    @classmethod
    def show_about(cls, parent: QWidget | None = None) -> None:
        """Helper to show the dialog."""
        dlg = cls(parent)
        dlg.exec()
