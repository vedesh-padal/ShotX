"""ShotX Central Theme.

Provides a unified palette and style utilities to harmonize the app's
look and feel with the official documentation branding.
"""

from __future__ import annotations


class Theme:
    """Centralized color palette and QSS utilities."""

    # --- Core Colors ---
    # Sophisticated dark gray (slightly lighter than pure black)
    BASE_DARK = "#1e1f22"
    BASE_LIGHTER = "#2b2d31"

    # Material Deep Purple from documentation branding
    ACCENT_PURPLE = "#673ab7"
    ACCENT_HOVER = "#7e57c2"
    ACCENT_PRESSED = "#5e35b1"

    # Text Colors
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#b5bac1"
    TEXT_MUTED = "#72767d"

    # Glassmorphism (Faux)
    # 80% opaque dark gray for that "frosted glass" look
    GLASS_BG = "rgba(15, 16, 18, 0.85)"
    GLASS_BORDER = "1px solid rgba(255, 255, 255, 0.08)"

    @staticmethod
    def get_sidebar_qss(font_size: int = 14) -> str:
        """Get stylized QSS for the main window sidebar."""
        return f"""
            QPushButton {{
                text-align: left;
                padding: 8px 20px;
                border: none;
                border-radius: 6px;
                font-size: {font_size}px;
                color: {Theme.TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:checked, QPushButton:pressed {{
                background-color: {Theme.ACCENT_PURPLE};
                color: #ffffff;
            }}
            QPushButton::menu-indicator {{
                subcontrol-position: right center;
                subcontrol-origin: padding;
                right: 8px;
            }}
            QMenu {{
                background-color: {Theme.BASE_LIGHTER};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 8px 24px;
                color: {Theme.TEXT_SECONDARY};
                border-radius: 4px;
                margin: 2px 6px;
            }}
            QMenu::item:selected {{
                background-color: {Theme.ACCENT_PURPLE};
                color: #ffffff;
            }}
        """

    @staticmethod
    def get_glass_dialog_qss() -> str:
        """Get the faux-glassmorphism style for dialogs."""
        return f"""
            QDialog {{
                background-color: {Theme.BASE_DARK};
                border: {Theme.GLASS_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton {{
                background-color: {Theme.ACCENT_PURPLE};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT_PRESSED};
            }}
            a {{
                color: {Theme.ACCENT_PURPLE};
                text-decoration: none;
            }}
        """

    @staticmethod
    def get_global_qss() -> str:
        """Get a baseline QSS for the entire application.

        We avoid setting background-color on 'QWidget' directly to prevent
        clobbering the internal styles of complex widgets like QListWidget, QTreeWidget, etc.
        """
        return f"""
            QMainWindow, QDialog {{
                background-color: {Theme.BASE_DARK};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
            }}
            QStatusBar {{
                background-color: {Theme.BASE_DARK};
                color: {Theme.TEXT_MUTED};
            }}
            QToolTip {{
                color: white;
                background-color: {Theme.BASE_LIGHTER};
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            QGroupBox {{
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                color: {Theme.ACCENT_PURPLE};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}

            /* Modern Global Scrollbars */
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.1);
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255, 255, 255, 0.2);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}

            QScrollBar:horizontal {{
                background: transparent;
                height: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(255, 255, 255, 0.1);
                min-width: 20px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
        """
