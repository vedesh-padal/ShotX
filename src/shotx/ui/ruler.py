"""Screen Ruler overlay to measure pixel distances and bounding boxes.

Renders the screen backdrop. Click and drag to measure width, height,
and the diagonal length (hypotenuse) between two points.
"""

from __future__ import annotations

import logging
import math
from PySide6.QtCore import Qt, QPoint, Signal, QRect
from PySide6.QtGui import QPainter, QImage, QColor, QPen, QFont, QPaintEvent, QMouseEvent, QKeyEvent, QPixmap, QCursor
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

class RulerOverlay(QWidget):
    """Fullscreen overlay for measuring distances on screen."""

    # Emitted when the user presses Esc or cancels
    cancelled = Signal()

    def __init__(self, backdrop: QImage | QPixmap) -> None:
        super().__init__()
        
        self._backdrop = backdrop
        
        self._start_pos: QPoint | None = None
        self._current_pos: QPoint | None = None
        self._is_dragging = False

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def show_fullscreen(self) -> None:
        """Show the overlay in fullscreen mode."""
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the backdrop and the measurement tools."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw the static screen backdrop
        painter.drawPixmap(0, 0, self._backdrop) if isinstance(self._backdrop, QPixmap) else painter.drawImage(0, 0, self._backdrop)

        # Draw a slight dimming overlay to make lines pop
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        if not self._start_pos or not self._current_pos:
            # If we're not measuring yet, maybe draw crosshairs at mouse?
            if self._current_pos:
                cx, cy = self._current_pos.x(), self._current_pos.y()
                painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
                painter.drawLine(0, cy, self.width(), cy)
                painter.drawLine(cx, 0, cx, self.height())
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        x1, y1 = self._start_pos.x(), self._start_pos.y()
        x2, y2 = self._current_pos.x(), self._current_pos.y()

        width = abs(x2 - x1)
        height = abs(y2 - y1)
        length = math.hypot(width, height)
        # angle = math.degrees(math.atan2(y2 - y1, x2 - x1))

        # 1. Draw bounding box (dashed)
        rect_pen = QPen(QColor(255, 255, 255, 120), 1, Qt.PenStyle.DashLine)
        painter.setPen(rect_pen)
        painter.setBrush(QColor(255, 255, 255, 20))
        
        rx = min(x1, x2)
        ry = min(y1, y2)
        painter.drawRect(rx, ry, width, height)

        # 2. Draw the diagonal line connecting the points
        line_pen = QPen(QColor(0, 200, 255, 255), 2)
        painter.setPen(line_pen)
        painter.drawLine(x1, y1, x2, y2)

        # 3. Draw start and end points
        painter.setBrush(QColor(0, 200, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self._start_pos, 4, 4)
        painter.drawEllipse(self._current_pos, 4, 4)

        # 4. Render tooltip info near the cursor
        box_width = 200
        box_height = 100
        
        # Offset cursor
        mag_x = x2 + 15
        mag_y = y2 + 15
        
        if mag_x + box_width > self.width():
            mag_x = x2 - box_width - 15  # flip left
        if mag_y + box_height > self.height():
            mag_y = y2 - box_height - 15 # flip up

        # Background for text
        painter.setBrush(QColor(30, 30, 30, 240))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(mag_x, mag_y, box_width, box_height, 4, 4)

        # Text constraints
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Cousine", 14, QFont.Weight.Bold))
        text_rect = QRect(mag_x + 15, mag_y + 10, box_width - 30, box_height - 20)
        
        info_text = (
            f"W: {width} px\n"
            f"H: {height} px\n"
            f"L: {length:.1f} px"
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, info_text)


    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._current_pos = self._start_pos
            self._is_dragging = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            if self._is_dragging or self._start_pos is not None:
                # Cancel current measure
                self._is_dragging = False
                self._start_pos = None
                self._current_pos = event.globalPosition().toPoint() # Switch back to crosshair
                self.update()
            else:
                self.cancelled.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._current_pos = event.globalPosition().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            # We don't clear the measurement here so they can read it.
            # A left click will restart it, right click will clear it.
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
