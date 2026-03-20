"""Color Picker overlay for extracting pixel colors from the screen.

Renders a magnified region around the cursor and displays the exact
RGB and HEX color values beneath it.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

class ColorPickerOverlay(QWidget):
    """Fullscreen overlay for selecting a color from the screen."""

    # Emitted when a color is successfully picked
    color_selected = Signal(QColor)
    # Emitted when the user presses Esc or cancels
    cancelled = Signal()

    def __init__(self, backdrop: QImage | QPixmap) -> None:
        super().__init__()
        # Ensure we always work with a QImage so we can reliably call .pixelColor()
        if isinstance(backdrop, QPixmap):
            self._backdrop = backdrop.toImage()
        else:
            self._backdrop = backdrop

        self._mouse_pos = QPoint(-1, -1)

        # Configuration for the magnifier
        self._zoom_factor = 12
        self._pixels_radius = 5  # Show an 11x11 grid total (5 left, 5 right, 1 center)

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        # Enable mouse tracking to update the magnifier constantly
        self.setMouseTracking(True)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the backdrop and the magnifier tool at the cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw the static screen backdrop
        painter.drawImage(0, 0, self._backdrop)

        if self._mouse_pos.x() < 0 or self._mouse_pos.y() < 0:
            return

        # The exact pixel we are hovering over
        cx, cy = self._mouse_pos.x(), self._mouse_pos.y()

        # Safely extract the center color (handling edge of screen)
        if self._backdrop.rect().contains(cx, cy):
            center_color = self._backdrop.pixelColor(cx, cy)
        else:
            center_color = QColor(0, 0, 0)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Determine where to draw the magnifier tool (offset from cursor so it doesn't block it)
        # We draw it slightly down and to the right, but if we are at the bottom right of the screen
        # we need to draw it up/left.
        mag_x = cx + 20
        mag_y = cy + 20

        # Calculate dynamic grid base size
        grid_size = (self._pixels_radius * 2 + 1) * self._zoom_factor

        # Ensure the box is wide enough to hold the text "RGB(255, 255, 255)"
        box_width = max(grid_size, 140)
        box_height = grid_size + 40  # Extra space for the text label at bottom

        # Center the grid horizontally inside the black box if box is wider than grid
        grid_offset_x = (box_width - grid_size) // 2

        # Keep inside screen bounds
        if mag_x + box_width > self.width():
            mag_x = cx - box_width - 20
        if mag_y + box_height > self.height():
            mag_y = cy - box_height - 20

        # Draw magnifier background/shadow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 30, 240))
        bg_rect = QRect(mag_x - 2, mag_y - 2, box_width + 4, box_height + 4)
        painter.drawRoundedRect(bg_rect, 4, 4)

        # Extract the small region of pixels around the cursor
        src_rect = QRect(
            cx - self._pixels_radius,
            cy - self._pixels_radius,
            self._pixels_radius * 2 + 1,
            self._pixels_radius * 2 + 1,
        )

        # We need to manually construct the magnified grid to handle screen boundaries safely
        painter.setPen(QColor(0, 0, 0, 50)) # Light grid lines
        for r_y in range(src_rect.height()):
            for r_x in range(src_rect.width()):
                px = src_rect.x() + r_x
                py = src_rect.y() + r_y

                # Fetch color, fallback to black if out of bounds
                if self._backdrop.rect().contains(px, py):
                    c = self._backdrop.pixelColor(px, py)
                else:
                    c = QColor(0, 0, 0)

                painter.setBrush(c)
                tile_rect = QRect(
                    mag_x + grid_offset_x + (r_x * self._zoom_factor),
                    mag_y + (r_y * self._zoom_factor),
                    self._zoom_factor,
                    self._zoom_factor
                )
                painter.drawRect(tile_rect)

        # Highlight the exact center pixel inside the grid
        painter.setPen(QPen(QColor(255, 0, 0, 200), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        center_rect = QRect(
            mag_x + grid_offset_x + (self._pixels_radius * self._zoom_factor),
            mag_y + (self._pixels_radius * self._zoom_factor),
            self._zoom_factor,
            self._zoom_factor
        )
        painter.drawRect(center_rect)

        # Draw the extracted color values
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Cousine", 9, QFont.Weight.Bold))

        hex_str = center_color.name().upper()
        rgb_str = f"RGB({center_color.red()}, {center_color.green()}, {center_color.blue()})"

        # Render the text block
        text_rect = QRect(mag_x, mag_y + grid_size, box_width, 40)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{hex_str}\n{rgb_str}")


    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._mouse_pos = event.globalPosition().toPoint()
        self.update()  # Trigger repaint for the magnifier

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            cx, cy = event.globalPosition().toPoint().x(), event.globalPosition().toPoint().y()
            if self._backdrop.rect().contains(cx, cy):
                color = self._backdrop.pixelColor(cx, cy)
                self.color_selected.emit(color)
            else:
                self.cancelled.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

    def wheelEvent(self, event) -> None:
        """Handle mouse wheel to change zoom level, clamping between 4x and 32x."""
        num_degrees = event.angleDelta().y() / 8
        num_steps = num_degrees / 15

        if num_steps > 0:
            self._zoom_factor = min(self._zoom_factor + 2, 32)
        elif num_steps < 0:
            self._zoom_factor = max(self._zoom_factor - 2, 4)

        self.update()
