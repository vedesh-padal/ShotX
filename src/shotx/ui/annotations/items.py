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
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Clamp movement to scene dimensions
            new_pos = value
            rect = self.scene().sceneRect()
            bbox = self.boundingRect()

            x = max(rect.left() - bbox.left(), min(new_pos.x(), rect.right() - bbox.right()))
            y = max(rect.top() - bbox.top(), min(new_pos.y(), rect.bottom() - bbox.bottom()))
            return QPointF(x, y)
        return super().itemChange(change, value)

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draws a dashed bounding box when the item is selected."""
        if self.isSelected():
            pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())


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

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self._rect)
        stroker = QPainterPathStroker()
        stroker.setWidth(self.thickness + 4)  # +4 for easier clicking
        return stroker.createStroke(path)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._rect)
        self._draw_selection_highlight(painter)


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

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(self._rect)
        stroker = QPainterPathStroker()
        stroker.setWidth(self.thickness + 4)
        return stroker.createStroke(path)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self._rect)
        self._draw_selection_highlight(painter)


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
        head_len = self._head_length()
        p = head_len + self.thickness
        return QRectF(self._start, self._end).normalized().adjusted(-p, -p, p, p)

    def _head_length(self) -> float:
        """Arrow head length scales with pen thickness."""
        return 10.0 + self.thickness * 2.0

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self._start)
        path.lineTo(self._end)

        # Stroke the line segment
        stroker = QPainterPathStroker()
        stroker.setWidth(self.thickness + 4)
        stroke_path = stroker.createStroke(path)

        # Compute and add the arrowhead polygon directly to the shape
        dx = self._end.x() - self._start.x()
        dy = self._end.y() - self._start.y()
        length = math.hypot(dx, dy)
        if length >= 1:
            ux, uy = dx / length, dy / length
            head_len = self._head_length()
            head_width = head_len * 0.5

            base_x = self._end.x() - ux * head_len
            base_y = self._end.y() - uy * head_len
            perp_x, perp_y = -uy, ux
            left = QPointF(base_x + perp_x * head_width, base_y + perp_y * head_width)
            right = QPointF(base_x - perp_x * head_width, base_y - perp_y * head_width)

            head_path = QPainterPath()
            head_path.addPolygon(QPolygonF([self._end, left, right]))
            stroke_path.addPath(head_path)

        return stroke_path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
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

        # Arrow head dimensions — scale with thickness
        head_len = self._head_length()
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
        self._draw_selection_highlight(painter)


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

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(self.thickness + 4)
        return stroker.createStroke(self._path)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        self._draw_selection_highlight(painter)


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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # Start in editing mode
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Clamp movement to scene dimensions
            new_pos = value
            rect = self.scene().sceneRect()
            bbox = self.boundingRect()

            x = max(rect.left() - bbox.left(), min(new_pos.x(), rect.right() - bbox.right()))
            y = max(rect.top() - bbox.top(), min(new_pos.y(), rect.bottom() - bbox.bottom()))
            return QPointF(x, y)
        return super().itemChange(change, value)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()

    def focusOutEvent(self, event) -> None:
        """When focus is lost, freeze the text and switch to non-editable."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # If user typed nothing, remove ourselves
        if not self.toPlainText().strip() and self.scene():
            self.scene().removeItem(self)
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click to re-enter editing mode."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        """Handle Ctrl+Shift+Plus/Minus for font resizing."""
        mods = event.modifiers()
        ctrl_shift = (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        )
        if mods & ctrl_shift == ctrl_shift:
            key = event.key()
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._change_font_size(2)
                event.accept()
                return
            elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                self._change_font_size(-2)
                event.accept()
                return
        super().keyPressEvent(event)

    def _change_font_size(self, delta: int) -> None:
        """Adjust font size by delta, clamped to [8, 72]."""
        font = self.font()
        new_size = max(8, min(72, font.pointSize() + delta))
        font.setPointSize(new_size)
        self.setFont(font)


# ---------------------------------------------------------------------------
# Highlight (semi-transparent marker)
# ---------------------------------------------------------------------------

class HighlightItem(BaseAnnotationItem):
    """A semi-transparent filled rectangle, like a highlighter pen."""

    ALPHA = 80  # ~30% opacity

    def __init__(self, start_pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        self._start = QPointF(start_pos)
        self._rect = QRectF(start_pos, start_pos)

    def set_end_pos(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(self._start, pos).normalized()

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        fill = QColor(self.color)
        fill.setAlpha(self.ALPHA)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill))
        painter.drawRect(self._rect)
        self._draw_selection_highlight(painter)


# ---------------------------------------------------------------------------
# Step Number
# ---------------------------------------------------------------------------

class StepNumberItem(BaseAnnotationItem):
    """A numbered circle for step-by-step guides.

    Each instance gets the next number from a class-level counter.
    The counter resets when the scene is cleared.
    """

    _counter: int = 0  # class-level auto-increment
    RADIUS = 16

    def __init__(self, pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        StepNumberItem._counter += 1
        self._number = StepNumberItem._counter
        self._center = QPointF(pos)

    @classmethod
    def reset_counter(cls) -> None:
        cls._counter = 0

    def boundingRect(self) -> QRectF:
        r = self.RADIUS + self.thickness
        return QRectF(
            self._center.x() - r, self._center.y() - r,
            r * 2, r * 2,
        )

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        r = self.RADIUS
        # Filled circle
        painter.setPen(QPen(self.color, self.thickness))
        painter.setBrush(QBrush(self.color))
        painter.drawEllipse(self._center, r, r)

        # Number text (white on colored background)
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("sans-serif", int(r * 0.9))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, str(self._number))
        self._draw_selection_highlight(painter)


# ---------------------------------------------------------------------------
# Blur / Pixelate
# ---------------------------------------------------------------------------

class BlurItem(BaseAnnotationItem):
    """A rectangle that pixelates the backdrop underneath.

    The effect is achieved by downscaling the backdrop region to a
    very small size (e.g. 8x8) then upscaling it back, producing
    a mosaic / pixelation effect. This is done at paint time using
    the stored backdrop reference.
    """

    PIXEL_SIZE = 8  # How many pixels wide each mosaic block is

    def __init__(
        self, start_pos: QPointF, color: QColor, thickness: int,
        backdrop: QImage | None = None,
    ) -> None:
        super().__init__(color, thickness)
        self._start = QPointF(start_pos)
        self._rect = QRectF(start_pos, start_pos)
        self._backdrop = backdrop

    def set_end_pos(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(self._start, pos).normalized()

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        rect = self._rect.toRect()
        if rect.isEmpty() or self._backdrop is None:
            return

        # Crop the backdrop region that this item covers
        crop = self._backdrop.copy(rect)
        if crop.isNull():
            return

        # Downscale to create pixelation, then upscale back
        w, h = max(1, rect.width() // self.PIXEL_SIZE), max(1, rect.height() // self.PIXEL_SIZE)
        tiny = crop.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        pixelated = tiny.scaled(rect.width(), rect.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)

        painter.drawImage(self._rect, pixelated)

        # Optional: draw a subtle dashed border so user can see the region
        pen = QPen(QColor(255, 255, 255, 60), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._rect)
        self._draw_selection_highlight(painter)


# ---------------------------------------------------------------------------
# Crop (Interactive Selection Box)
# ---------------------------------------------------------------------------

class CropItem(QGraphicsItem):
    """An interactive dashed rectangle representing a crop selection with resize handles."""

    def __init__(self, start_pos: QPointF) -> None:
        super().__init__()
        self._start = QPointF(start_pos)
        self._rect = QRectF(start_pos, start_pos)
        self.setZValue(9999)  # Draw above everything else

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self._drag_edge: str | None = None
        self._drag_start_rect = QRectF()
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def set_end_pos(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(self._start, pos).normalized()

    def get_crop_rect(self) -> QRectF:
        """Return the final rounded rectangle to crop in scene coordinates."""
        return self.sceneTransform().mapRect(self._rect)

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-6, -6, 6, 6)

    def _get_edge(self, pos: QPointF) -> str:
        r = self._rect
        m = 15 # larger margin for handles for easier grabbing
        if pos.x() <= r.left() + m and pos.y() <= r.top() + m:
            return "top-left"
        if pos.x() >= r.right() - m and pos.y() >= r.bottom() - m:
            return "bottom-right"
        if pos.x() >= r.right() - m and pos.y() <= r.top() + m:
            return "top-right"
        if pos.x() <= r.left() + m and pos.y() >= r.bottom() - m:
            return "bottom-left"
        if pos.y() <= r.top() + m:
            return "top"
        if pos.y() >= r.bottom() - m:
            return "bottom"
        if pos.x() <= r.left() + m:
            return "left"
        if pos.x() >= r.right() - m:
            return "right"
        return "center"

    def hoverMoveEvent(self, event) -> None:
        edge = self._get_edge(event.pos())
        if edge in ("top-left", "bottom-right"):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif edge in ("top-right", "bottom-left"):
            self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
        elif edge in ("top", "bottom"):
            self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        elif edge in ("left", "right"):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._drag_edge = self._get_edge(event.pos())
        self._drag_start_rect = self._rect
        if self._drag_edge != "center":
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_edge and self._drag_edge != "center":
            s_pos = event.scenePos()
            scene_rect = self.scene().sceneRect()

            # Clamp the grabbed edge position to the scene boundary
            x = max(scene_rect.left(), min(s_pos.x(), scene_rect.right()))
            y = max(scene_rect.top(), min(s_pos.y(), scene_rect.bottom()))
            pos = self.mapFromScene(QPointF(x, y))

            r = QRectF(self._drag_start_rect)
            min_size = 20

            if "left" in self._drag_edge:
                r.setLeft(min(pos.x(), r.right() - min_size))
            if "right" in self._drag_edge:
                r.setRight(max(pos.x(), r.left() + min_size))
            if "top" in self._drag_edge:
                r.setTop(min(pos.y(), r.bottom() - min_size))
            if "bottom" in self._drag_edge:
                r.setBottom(max(pos.y(), r.top() + min_size))

            self.prepareGeometryChange()
            self._rect = r
        else:
            super().mouseMoveEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            r = self._rect
            scene_rect = self.scene().sceneRect()

            # Avoid dragging crop box off the canvas
            x = new_pos.x()
            y = new_pos.y()
            if x + r.left() < scene_rect.left():
                x = scene_rect.left() - r.left()
            if x + r.right() > scene_rect.right():
                x = scene_rect.right() - r.right()
            if y + r.top() < scene_rect.top():
                y = scene_rect.top() - r.top()
            if y + r.bottom() > scene_rect.bottom():
                y = scene_rect.bottom() - r.bottom()

            return QPointF(x, y)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_edge = None
        super().mouseReleaseEvent(event)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        if self._rect.width() < 1 or self._rect.height() < 1:
            return

        pen = QPen(Qt.GlobalColor.white, 2, Qt.PenStyle.DashLine)

        # Outer black solid line for contrast
        painter.setPen(QPen(Qt.GlobalColor.black, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._rect)

        # Inner white dashed line
        painter.setPen(pen)
        painter.drawRect(self._rect)

        # Draw handles
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(Qt.GlobalColor.white))

        r = self._rect
        s = 8  # handle size
        points = [
            QPointF(r.left(), r.top()), QPointF(r.center().x(), r.top()), QPointF(r.right(), r.top()),
            QPointF(r.left(), r.center().y()),                            QPointF(r.right(), r.center().y()),
            QPointF(r.left(), r.bottom()), QPointF(r.center().x(), r.bottom()), QPointF(r.right(), r.bottom()),
        ]

        for p in points:
            painter.drawRect(QRectF(p.x() - s/2, p.y() - s/2, s, s))
