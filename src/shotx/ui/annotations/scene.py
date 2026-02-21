"""Graphics scene for handling drawing interactions."""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QUndoStack
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from .items import BaseAnnotationItem, RectangleItem

logger = logging.getLogger(__name__)


class AnnotationTool(Enum):
    """The active drawing tool."""
    NONE = auto()
    SELECT = auto()  # Move/Resize existing items
    ARROW = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    TEXT = auto()
    FREEHAND = auto()
    BLUR = auto()


class AnnotationScene(QGraphicsScene):
    """A self-contained scene for drawing vectors over the screenshot."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.undo_stack = QUndoStack(self)
        
        self.current_tool = AnnotationTool.RECTANGLE
        self.current_color = QColor(255, 0, 0)
        self.current_thickness = 4
        
        self._active_item: Optional[BaseAnnotationItem] = None
        
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        if self.current_tool == AnnotationTool.SELECT:
            super().mousePressEvent(event)
            return

        # Start drawing a new shape
        pos = event.scenePos()
        
        if self.current_tool == AnnotationTool.RECTANGLE:
            self._active_item = RectangleItem(pos, self.current_color, self.current_thickness)
            self.addItem(self._active_item)
            
        # Stop default behavior (prevents dragging other items underneath)
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._active_item and isinstance(self._active_item, RectangleItem):
            self._active_item.set_end_pos(event.scenePos())
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._active_item:
            # Finished drawing
            # TODO: We should actually use a QUndoCommand here so it can be un-drawn!
            # For now, just drop the reference
            self._active_item = None
            event.accept()
            return

        super().mouseReleaseEvent(event)
