"""Custom graphics items for the annotation editor."""

from __future__ import annotations

import logging
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsLineItem

logger = logging.getLogger(__name__)


class BaseAnnotationItem(QGraphicsItem):
    """Base class for all drawn annotations."""

    def __init__(self, color: QColor, thickness: int) -> None:
        super().__init__()
        self.color = color
        self.thickness = thickness
        self._pen = QPen(self.color, self.thickness)
        
        # Items should be selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        
    # Standard graphics item methods to be implemented
    # boundingRect()
    # paint()


class RectangleItem(BaseAnnotationItem):
    """A drawable rectangle."""

    def __init__(self, start_pos: QPointF, color: QColor, thickness: int) -> None:
        super().__init__(color, thickness)
        self._rect = QRectF(start_pos, start_pos)

    def set_end_pos(self, pos: QPointF) -> None:
        """Update the rectangle dimensions as the user drags."""
        self.prepareGeometryChange()
        self._rect.setBottomRight(pos)
        self._rect = self._rect.normalized()

    def boundingRect(self) -> QRectF:
        # Pad bounding rect to account for pen thickness
        padding = self.thickness / 2.0
        return self._rect.adjusted(-padding, -padding, padding, padding)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setPen(self._pen)
        painter.drawRect(self._rect)

# We will add Arrow, Ellipse, Text, etc. here incrementally.
