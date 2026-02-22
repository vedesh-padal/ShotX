"""Graphics scene for handling drawing interactions.

Manages the active tool, creates the appropriate item on mouse press,
updates it on mouse move, and finalizes on mouse release. Each drawing
action is wrapped in a QUndoCommand for Ctrl+Z / Ctrl+Y support.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QImage, QUndoStack, QUndoCommand, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from .items import (
    BaseAnnotationItem,
    RectangleItem,
    EllipseItem,
    ArrowItem,
    FreehandItem,
    EditableTextItem,
    HighlightItem,
    StepNumberItem,
    BlurItem,
)

logger = logging.getLogger(__name__)


class AnnotationTool(Enum):
    """The active drawing tool."""
    NONE = auto()
    SELECT = auto()     # Move/Resize existing items
    ARROW = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    TEXT = auto()
    FREEHAND = auto()
    BLUR = auto()
    HIGHLIGHT = auto()
    STEP_NUMBER = auto()
    ERASER = auto()


# ---------------------------------------------------------------------------
# Undo commands
# ---------------------------------------------------------------------------

class AddItemCommand(QUndoCommand):
    """Undoable command that adds a graphics item to the scene."""

    def __init__(self, scene: QGraphicsScene, item) -> None:
        super().__init__("Draw shape")
        self._scene = scene
        self._item = item

    def redo(self) -> None:
        if self._item.scene() is None:
            self._scene.addItem(self._item)

    def undo(self) -> None:
        self._scene.removeItem(self._item)


class RemoveItemCommand(QUndoCommand):
    """Undoable command that removes a graphics item from the scene."""

    def __init__(self, scene: QGraphicsScene, item) -> None:
        super().__init__("Erase shape")
        self._scene = scene
        self._item = item

    def redo(self) -> None:
        if self._item.scene() is not None:
            self._scene.removeItem(self._item)

    def undo(self) -> None:
        if self._item.scene() is None:
            self._scene.addItem(self._item)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class AnnotationScene(QGraphicsScene):
    """A self-contained scene for drawing vectors over the screenshot."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.undo_stack = QUndoStack(self)

        self.current_tool = AnnotationTool.RECTANGLE
        self.current_color = QColor(255, 0, 0)
        self.current_thickness = 4

        # Backdrop crop for blur tool (set by overlay)
        self.backdrop_crop: QImage | None = None

        self._active_item: Optional[BaseAnnotationItem] = None

    # ----- Mouse events -----

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        if self.current_tool == AnnotationTool.SELECT:
            super().mousePressEvent(event)
            return

        pos = event.scenePos()
        tool = self.current_tool
        color = self.current_color
        thick = self.current_thickness

        if tool == AnnotationTool.RECTANGLE:
            self._active_item = RectangleItem(pos, color, thick)
        elif tool == AnnotationTool.ELLIPSE:
            self._active_item = EllipseItem(pos, color, thick)
        elif tool == AnnotationTool.ARROW:
            self._active_item = ArrowItem(pos, color, thick)
        elif tool == AnnotationTool.FREEHAND:
            self._active_item = FreehandItem(pos, color, thick)
        elif tool == AnnotationTool.HIGHLIGHT:
            self._active_item = HighlightItem(pos, color, thick)
        elif tool == AnnotationTool.BLUR:
            self._active_item = BlurItem(pos, color, thick, backdrop=self.backdrop_crop)
        elif tool == AnnotationTool.TEXT:
            item = EditableTextItem(pos, color, thick)
            self.addItem(item)
            self.undo_stack.push(AddItemCommand(self, item))
            event.accept()
            return
        elif tool == AnnotationTool.STEP_NUMBER:
            item = StepNumberItem(pos, color, thick)
            self.addItem(item)
            self.undo_stack.push(AddItemCommand(self, item))
            event.accept()
            return
        elif tool == AnnotationTool.ERASER:
            item = self.itemAt(pos, QTransform())
            if item and (isinstance(item, BaseAnnotationItem) or isinstance(item, EditableTextItem)):
                self.undo_stack.push(RemoveItemCommand(self, item))
            event.accept()
            return
        else:
            event.accept()
            return

        # Add to scene immediately (visual feedback while dragging)
        self.addItem(self._active_item)
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self._active_item:
            super().mouseMoveEvent(event)
            return

        pos = event.scenePos()

        if isinstance(self._active_item, FreehandItem):
            self._active_item.add_point(pos)
        elif hasattr(self._active_item, "set_end_pos"):
            self._active_item.set_end_pos(pos)

        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._active_item:
            self.undo_stack.push(AddItemCommand(self, self._active_item))
            self._active_item = None
            event.accept()
            return

        super().mouseReleaseEvent(event)
