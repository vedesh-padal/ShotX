"""Custom graphics items for the annotation editor.

Each item subclasses BaseAnnotationItem which provides:
- color and thickness state
- selectable + movable flags
- a pre-built QPen

Drawing flow:
    1. mousePressEvent in AnnotationScene creates the item at start_pos
    2. mouseMoveEvent calls set_end_pos() to update geometry live
    3. mouseReleaseEvent finalizes — the item stays on the scene
"""

from __future__ import annotations

import logging
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QBrush,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem

logger = logging.getLogger(__name__)


class BaseAnnotationItem(QGraphicsItem):
    """Base class for all drawn annotations."""

    def __init__(self, color: QColor, thickness: int) -> None:
        super().__init__()
        self.color = color
        self.thickness = thickness
        self._pen = QPen(self.color, self.thickness)
        self._pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        # Items should be selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------

class RectangleItem(BaseAnnotationItem):
    """A drawable rectangle (outline only)."""

    def __init__(self, start_pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        self._start = QPointF(start_pos)
        self._rect = QRectF(start_pos, start_pos)

    def set_end_pos(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(self._start, pos).normalized()

    def boundingRect(self) -> QRectF:
        p = self.thickness / 2.0
        return self._rect.adjusted(-p, -p, p, p)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._rect)


# ---------------------------------------------------------------------------
# Ellipse
# ---------------------------------------------------------------------------

class EllipseItem(BaseAnnotationItem):
    """A drawable ellipse (outline only)."""

    def __init__(self, start_pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        self._start = QPointF(start_pos)
        self._rect = QRectF(start_pos, start_pos)

    def set_end_pos(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(self._start, pos).normalized()

    def boundingRect(self) -> QRectF:
        p = self.thickness / 2.0
        return self._rect.adjusted(-p, -p, p, p)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self._rect)


# ---------------------------------------------------------------------------
# Arrow
# ---------------------------------------------------------------------------

class ArrowItem(BaseAnnotationItem):
    """A line with a triangular arrowhead at the end point.

    The arrowhead is drawn as a filled triangle whose size scales
    with the pen thickness so it always looks proportional.
    """

    ARROW_SIZE = 14  # base arrow head length in pixels

    def __init__(self, start_pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        self._start = QPointF(start_pos)
        self._end = QPointF(start_pos)

    def set_end_pos(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._end = QPointF(pos)

    def boundingRect(self) -> QRectF:
        p = self.ARROW_SIZE + self.thickness
        return QRectF(self._start, self._end).normalized().adjusted(-p, -p, p, p)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setPen(self._pen)

        # Draw the line
        painter.drawLine(self._start, self._end)

        # Draw arrowhead
        dx = self._end.x() - self._start.x()
        dy = self._end.y() - self._start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return

        # Unit vector from start → end
        ux, uy = dx / length, dy / length

        # Arrow head dimensions
        head_len = self.ARROW_SIZE
        head_width = head_len * 0.5

        # Base of the arrowhead (point along the line, behind the tip)
        base_x = self._end.x() - ux * head_len
        base_y = self._end.y() - uy * head_len

        # Perpendicular offsets
        perp_x, perp_y = -uy, ux
        left = QPointF(base_x + perp_x * head_width, base_y + perp_y * head_width)
        right = QPointF(base_x - perp_x * head_width, base_y - perp_y * head_width)

        arrow_head = QPolygonF([self._end, left, right])
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow_head)


# ---------------------------------------------------------------------------
# Freehand
# ---------------------------------------------------------------------------

class FreehandItem(BaseAnnotationItem):
    """A freehand drawing using QPainterPath.

    Points are accumulated into a QPainterPath during the drag.
    """

    def __init__(self, start_pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        self._path = QPainterPath(start_pos)

    def add_point(self, pos: QPointF) -> None:
        """Append a point (called on every mouse move during drag)."""
        self.prepareGeometryChange()
        self._path.lineTo(pos)

    def boundingRect(self) -> QRectF:
        p = self.thickness / 2.0
        return self._path.boundingRect().adjusted(-p, -p, p, p)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)


# ---------------------------------------------------------------------------
# Text (inline-editable)
# ---------------------------------------------------------------------------

class EditableTextItem(QGraphicsTextItem):
    """A text annotation that supports inline editing.

    Inherits from QGraphicsTextItem directly (not BaseAnnotationItem)
    because QGraphicsTextItem has its own paint/boundingRect/editing
    machinery. We mirror the same color/selectable/movable behavior.

    The item starts in editing mode (blinking cursor, typing) and
    switches to non-editable when the user clicks elsewhere.
    """

    DEFAULT_FONT_SIZE = 18

    def __init__(self, pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__()
        self.setPos(pos)
        self.setDefaultTextColor(color)

        font = QFont("sans-serif", self.DEFAULT_FONT_SIZE)
        font.setBold(True)
        self.setFont(font)

        # Selectable + movable (same as BaseAnnotationItem)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        # Start in editing mode
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()

    def focusOutEvent(self, event) -> None:
        """When focus is lost, freeze the text and switch to non-editable."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # If user typed nothing, remove ourselves
        if not self.toPlainText().strip():
            if self.scene():
                self.scene().removeItem(self)
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click to re-enter editing mode."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()
        super().mouseDoubleClickEvent(event)

