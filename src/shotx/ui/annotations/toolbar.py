"""Floating toolbar for the annotation editor."""

from __future__ import annotations

import logging
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QButtonGroup, QLabel,
)

from .scene import AnnotationTool

logger = logging.getLogger(__name__)


class _HoverButton(QPushButton):
    """QPushButton that emits hover signals for inline label updates."""
    
    hovered = Signal(str)   # emits the tooltip text on enter
    unhovered = Signal()    # emits on leave
    
    def __init__(self, text: str, hover_text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._hover_text = hover_text
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    
    def enterEvent(self, event: QEvent) -> None:
        self.hovered.emit(self._hover_text)
        super().enterEvent(event)
        
    def leaveEvent(self, event: QEvent) -> None:
        self.unhovered.emit()
        super().leaveEvent(event)


class AnnotationToolbar(QWidget):
    """A floating horizontal toolbar with annotation tools."""
    
    tool_selected = Signal(AnnotationTool)
    accept_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        # No window flags — this is now a plain child widget of the overlay
        # This avoids all the Wayland tooltip/focus issues
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(2)
        
        # --- Main button row ---
        self.bg_widget = QWidget(self)
        self.bg_widget.setStyleSheet(
            "background-color: rgba(30, 30, 30, 240);"
            "border-radius: 6px;"
            "border: 1px solid rgba(255, 255, 255, 40);"
        )
        btn_layout = QHBoxLayout(self.bg_widget)
        btn_layout.setContentsMargins(8, 4, 8, 4)
        btn_layout.setSpacing(8)
        outer_layout.addWidget(self.bg_widget)
        
        # --- Inline hover label (replaces unreliable native QToolTip) ---
        self._hover_label = QLabel("", self)
        self._hover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hover_label.setStyleSheet(
            "color: rgba(255, 255, 255, 180);"
            "font-size: 11px;"
            "background: transparent;"
            "padding: 0px;"
        )
        self._hover_label.setFixedHeight(16)
        outer_layout.addWidget(self._hover_label)
        
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        
        # Tool buttons
        self._add_tool_btn("👆", "Select (Move/Resize)", AnnotationTool.SELECT, btn_layout)
        self._add_tool_btn("⬛", "Rectangle", AnnotationTool.RECTANGLE, btn_layout, checked=True)
        self._add_tool_btn("↗", "Arrow", AnnotationTool.ARROW, btn_layout)
        self._add_tool_btn("T", "Text", AnnotationTool.TEXT, btn_layout)
        self._add_tool_btn("✎", "Freehand", AnnotationTool.FREEHAND, btn_layout)
        
        self.tool_group.idClicked.connect(self._on_tool_clicked)
        
        # Separator
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 50);")
        btn_layout.addWidget(sep)
        
        # Action buttons
        self._add_action_btn("✔", "Accept & Save (Enter)", "#28a745", btn_layout, self.accept_requested.emit)
        self._add_action_btn("✕", "Cancel (Escape)", "#dc3545", btn_layout, self.cancel_requested.emit)

    def _add_tool_btn(
        self, icon_text: str, hover_text: str, tool: AnnotationTool,
        layout: QHBoxLayout, checked: bool = False,
    ) -> None:
        btn = _HoverButton(icon_text, hover_text, self.bg_widget)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedSize(32, 32)
        btn.setStyleSheet(self._button_style())
        btn.hovered.connect(self._show_hover)
        btn.unhovered.connect(self._clear_hover)
        
        self.tool_group.addButton(btn, id=tool.value)
        layout.addWidget(btn)
        
    def _add_action_btn(
        self, icon_text: str, hover_text: str, color: str,
        layout: QHBoxLayout, callback,
    ) -> None:
        btn = _HoverButton(icon_text, hover_text, self.bg_widget)
        btn.setFixedSize(32, 32)
        btn.setStyleSheet(self._button_style(color=color))
        btn.hovered.connect(self._show_hover)
        btn.unhovered.connect(self._clear_hover)
        btn.clicked.connect(callback)
        layout.addWidget(btn)

    def _button_style(self, color: str = "#ffffff") -> str:
        return f"""
        QPushButton {{
            background-color: transparent;
            color: {color};
            border-radius: 4px;
            font-size: 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: rgba(255, 255, 255, 30);
        }}
        QPushButton:checked {{
            background-color: rgba(0, 174, 255, 80);
            border: 1px solid rgba(0, 174, 255, 200);
        }}
        """

    def _show_hover(self, text: str) -> None:
        self._hover_label.setText(text)
        
    def _clear_hover(self) -> None:
        self._hover_label.setText("")

    def _on_tool_clicked(self, tool_id: int) -> None:
        self.tool_selected.emit(AnnotationTool(tool_id))
