"""Floating toolbar for the annotation editor."""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .scene import AnnotationTool

logger = logging.getLogger(__name__)


class _HoverButton(QPushButton):
    """QPushButton that emits hover signals for inline label updates."""

    hovered = Signal(str)   # emits the tooltip text on enter
    unhovered = Signal()    # emits on leave
    right_clicked = Signal() # emits on right-click release

    def __init__(self, text: str, hover_text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._hover_text = hover_text
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    from PySide6.QtGui import QEnterEvent
    def enterEvent(self, event: QEnterEvent) -> None:
        self.hovered.emit(self._hover_text)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.unhovered.emit()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class AnnotationToolbar(QWidget):
    """A floating horizontal toolbar with annotation tools."""

    tool_selected = Signal(AnnotationTool)
    color_changed = Signal(QColor)
    thickness_changed = Signal(int)
    accept_requested = Signal()
    cancel_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()

    # Size constants
    BTN_SIZE = 40
    SEP_HEIGHT = 28

    def __init__(
        self,
        initial_color: QColor | None = None,
        parent: QWidget | None = None,
    ) -> None:
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
            "color: rgba(255, 255, 255, 220);"
            "font-size: 12px;"
            "font-weight: bold;"
            "background: transparent;"
            "padding: 0px;"
        )
        self._hover_label.setFixedHeight(18)
        outer_layout.addWidget(self._hover_label)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        # Tool buttons
        self._add_tool_btn("👆", "Select (Move/Resize)", AnnotationTool.SELECT, btn_layout)
        self._add_tool_btn("⬛", "Rectangle", AnnotationTool.RECTANGLE, btn_layout, checked=True)
        self._add_tool_btn("⬭", "Ellipse", AnnotationTool.ELLIPSE, btn_layout)
        self._add_tool_btn("↗", "Arrow", AnnotationTool.ARROW, btn_layout)
        self._add_tool_btn("T", "Text", AnnotationTool.TEXT, btn_layout)
        self._add_tool_btn("✎", "Freehand", AnnotationTool.FREEHAND, btn_layout)
        self._add_tool_btn("✂", "Crop (Drag box, hit Enter)", AnnotationTool.CROP, btn_layout)
        self._add_tool_btn("▓", "Blur / Pixelate", AnnotationTool.BLUR, btn_layout)
        self._add_tool_btn("🖍", "Highlight", AnnotationTool.HIGHLIGHT, btn_layout)

        from .items import StepNumberItem
        self._add_tool_btn(
            "#", "Step Number (Right-Click to reset)", AnnotationTool.STEP_NUMBER,
            btn_layout, right_click_callback=StepNumberItem.reset_counter
        )
        self._add_tool_btn("🗑", "Erase", AnnotationTool.ERASER, btn_layout)

        self.tool_group.idClicked.connect(self._on_tool_clicked)

        # Separator
        self._add_separator(btn_layout)

        # Undo / Redo
        self._add_action_btn("↩", "Undo (Ctrl+Z)", "#aaaaaa", btn_layout, self.undo_requested.emit)
        self._add_action_btn("↪", "Redo (Ctrl+Y)", "#aaaaaa", btn_layout, self.redo_requested.emit)

        # Separator
        self._add_separator(btn_layout)

        # Color swatch button
        self._color_btn = _HoverButton("●", "Change Color", self.bg_widget)
        self._color_btn.setFixedSize(self.BTN_SIZE, self.BTN_SIZE)
        self._current_color = initial_color or QColor(255, 0, 0)
        self._update_color_btn_style()
        self._color_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._color_btn.clicked.connect(self._pick_color)
        self._color_btn.hovered.connect(self._show_hover)
        self._color_btn.unhovered.connect(self._clear_hover)
        btn_layout.addWidget(self._color_btn)

        # Separator
        self._add_separator(btn_layout)

        # Action buttons
        self._add_action_btn("✔", "Accept & Save (Enter)", "#28a745", btn_layout, self.accept_requested.emit)
        self._add_action_btn("✕", "Cancel (Escape)", "#dc3545", btn_layout, self.cancel_requested.emit)

        # Separator
        self._add_separator(btn_layout)

        # Thickness presets
        self._thickness_group = QButtonGroup(self)
        self._thickness_group.setExclusive(True)
        for label, val in [("╌", 2), ("─", 4), ("━", 8)]:
            btn = _HoverButton(label, f"Thickness: {val}px", self.bg_widget)
            btn.setCheckable(True)
            btn.setChecked(val == 4)  # default
            btn.setFixedSize(self.BTN_SIZE, self.BTN_SIZE)
            btn.setStyleSheet(self._button_style())
            btn.hovered.connect(self._show_hover)
            btn.unhovered.connect(self._clear_hover)
            self._thickness_group.addButton(btn, id=val)
            btn_layout.addWidget(btn)
        self._thickness_group.idClicked.connect(lambda v: self.thickness_changed.emit(v))

    def _add_tool_btn(
        self, icon_text: str, hover_text: str, tool: AnnotationTool,
        layout: QHBoxLayout, checked: bool = False, right_click_callback=None
    ) -> None:
        btn = _HoverButton(icon_text, hover_text, self.bg_widget)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedSize(self.BTN_SIZE, self.BTN_SIZE)
        btn.setStyleSheet(self._button_style())
        btn.hovered.connect(self._show_hover)
        btn.unhovered.connect(self._clear_hover)

        if right_click_callback:
            btn.right_clicked.connect(right_click_callback)

        self.tool_group.addButton(btn, id=tool.value)
        layout.addWidget(btn)

    def _add_action_btn(
        self, icon_text: str, hover_text: str, color: str,
        layout: QHBoxLayout, callback,
    ) -> None:
        btn = _HoverButton(icon_text, hover_text, self.bg_widget)
        btn.setFixedSize(self.BTN_SIZE, self.BTN_SIZE)
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
            border-radius: 6px;
            font-size: 20px;
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

    def _add_separator(self, layout: QHBoxLayout) -> None:
        sep = QWidget(self.bg_widget)
        sep.setFixedWidth(1)
        sep.setFixedHeight(self.SEP_HEIGHT)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 50);")
        layout.addWidget(sep)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._current_color, self, "Annotation Color")
        if color.isValid():
            self._current_color = color
            self._update_color_btn_style()
            self.color_changed.emit(color)

    def _update_color_btn_style(self) -> None:
        c = self._current_color.name()  # e.g. "#ff0000"
        self._color_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {c};
            border-radius: 6px;
            font-size: 26px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: rgba(255, 255, 255, 30);
        }}
        """)
