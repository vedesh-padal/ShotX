"""Region selection overlay widget.

Displays a fullscreen frozen screenshot as a backdrop, allowing the user
to select a region by clicking and dragging. The area outside the selection
is darkened with a semi-transparent mask.

Architecture:
    The overlay does NOT capture the screen — it receives a pre-captured
    QImage (from the portal or grabWindow) and displays it fullscreen.
    This is the same approach ShareX and Flameshot use.

Rendering layers (bottom to top):
    1. Frozen screenshot backdrop
    2. Dark overlay mask (everywhere except selection)
    3. Auto-detect region highlights (on hover, before drag)
    4. Selection rectangle with border
    5. Dimension label (WxH near selection)
    6. Crosshair lines through cursor position

State machine:
    IDLE → HOVERING (mouse moves, regions highlight)
         → SELECTING (mouse press + drag)
         → DONE (mouse release / Enter)
    Escape / Right-click → CANCELLED
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class OverlayState(Enum):
    """States of the region selection overlay."""

    IDLE = auto()       # Waiting for user interaction
    HOVERING = auto()   # Mouse moving, auto-detect regions highlight
    SELECTING = auto()  # Mouse pressed, dragging selection
    DONE = auto()       # Selection confirmed
    CANCELLED = auto()  # User pressed Escape


@dataclass
class DetectRegion:
    """A detectable region on screen (window or widget).

    Used for auto-detect highlighting — when the cursor hovers
    over a region, it gets highlighted so the user can click to select.
    """

    rect: QRect
    label: str       # e.g. "Firefox", "Save Button"
    depth: int = 0   # Nesting depth: 0=window, 1=panel, 2=button, etc.


class RegionOverlay(QWidget):
    """Fullscreen overlay for region selection.

    Signals:
        region_selected(QRect): Emitted when user confirms a selection.
        selection_cancelled(): Emitted when user cancels (Escape).
    """

    region_selected = Signal(QRect)
    selection_cancelled = Signal()

    # --- Visual constants ---
    MASK_COLOR = QColor(0, 0, 0, 128)          # Semi-transparent black overlay
    SELECTION_BORDER = QColor(0, 174, 255)     # Bright blue border
    SELECTION_BORDER_WIDTH = 2
    HIGHLIGHT_COLOR = QColor(0, 174, 255, 60)  # Light blue for auto-detect hover
    HIGHLIGHT_BORDER = QColor(0, 174, 255, 180)
    CROSSHAIR_COLOR = QColor(255, 255, 255, 100)
    DIM_LABEL_BG = QColor(0, 0, 0, 180)       # Dark background for dimension label
    DIM_LABEL_FG = QColor(255, 255, 255)       # White text

    def __init__(
        self,
        backdrop: QImage,
        regions: list[DetectRegion] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._backdrop = backdrop
        self._backdrop_pixmap = QPixmap.fromImage(backdrop)
        self._regions = regions or []

        # Sort regions by area (smallest first) so hit-testing finds
        # the most specific (innermost) region first
        self._regions.sort(key=lambda r: r.rect.width() * r.rect.height())

        # State
        self._state = OverlayState.IDLE
        self._mouse_pos = QPoint(0, 0)

        # Selection rectangle (from drag)
        self._selection_start = QPoint(0, 0)
        self._selection_rect = QRect()

        # Currently highlighted auto-detect region
        self._hovered_region: DetectRegion | None = None

        # Window setup — fullscreen, frameless, on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # Don't show in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        # Size to full screen
        self.setFixedSize(backdrop.width(), backdrop.height())

        logger.info(
            "Overlay created: %dx%d, %d detect regions",
            backdrop.width(),
            backdrop.height(),
            len(self._regions),
        )

    def show_fullscreen(self) -> None:
        """Show the overlay in fullscreen mode."""
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    @property
    def selected_rect(self) -> QRect:
        """The currently selected rectangle (may be empty)."""
        return self._selection_rect

    # --- Event handlers ---

    def paintEvent(self, event) -> None:
        """Render all overlay layers."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Layer 1: Frozen screenshot backdrop
        painter.drawPixmap(0, 0, self._backdrop_pixmap)

        # Layer 2: Dark mask (everywhere except selection)
        self._paint_mask(painter)

        # Layer 3: Auto-detect region highlight (hover)
        if self._hovered_region and self._state != OverlayState.SELECTING:
            self._paint_region_highlight(painter, self._hovered_region)

        # Layer 4: Selection rectangle
        if not self._selection_rect.isNull() and self._selection_rect.isValid():
            self._paint_selection(painter)

        # Layer 5: Dimension label
        if not self._selection_rect.isNull() and self._selection_rect.isValid():
            self._paint_dimensions(painter)

        # Layer 6: Crosshair
        if self._state in (OverlayState.IDLE, OverlayState.HOVERING):
            self._paint_crosshair(painter)

        # QPainter is automatically ended when it goes out of scope

    def mousePressEvent(self, event) -> None:
        """Start selection on left click."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()

            # If hovering over an auto-detect region, select it immediately
            if self._hovered_region and self._state == OverlayState.HOVERING:
                self._selection_rect = self._hovered_region.rect
                self._state = OverlayState.DONE
                self._confirm_selection()
                return

            # Start manual drag selection
            self._state = OverlayState.SELECTING
            self._selection_start = pos
            self._selection_rect = QRect(pos, QSize(0, 0))
            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event) -> None:
        """Update selection rectangle or hover detection."""
        self._mouse_pos = event.position().toPoint()

        if self._state == OverlayState.SELECTING:
            # Update selection rectangle from drag
            self._selection_rect = QRect(
                self._selection_start, self._mouse_pos
            ).normalized()
            self.update()
        else:
            # Auto-detect: find region under cursor
            old_hover = self._hovered_region
            self._hovered_region = self._find_region_at(
                self._mouse_pos.x(), self._mouse_pos.y()
            )
            if self._hovered_region:
                self._state = OverlayState.HOVERING
                self._selection_rect = self._hovered_region.rect
            else:
                self._state = OverlayState.IDLE
                self._selection_rect = QRect()

            # Only repaint if hover changed
            if self._hovered_region != old_hover:
                self.update()
            else:
                # Still update for crosshair movement
                self.update()

    def mouseReleaseEvent(self, event) -> None:
        """Finish selection on mouse release."""
        if event.button() == Qt.MouseButton.LeftButton and self._state == OverlayState.SELECTING:
            self._selection_rect = QRect(
                self._selection_start, event.position().toPoint()
            ).normalized()

            # Ignore tiny selections (accidental clicks)
            if self._selection_rect.width() < 5 or self._selection_rect.height() < 5:
                self._state = OverlayState.IDLE
                self._selection_rect = QRect()
                self.update()
                return

            self._state = OverlayState.DONE
            self._confirm_selection()

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self._cancel()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if not self._selection_rect.isNull() and self._selection_rect.isValid():
                self._confirm_selection()
        elif key == Qt.Key.Key_A and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+A: select entire screen
            self._selection_rect = QRect(0, 0, self.width(), self.height())
            self._state = OverlayState.DONE
            self._confirm_selection()

    # --- Private painting methods ---

    def _paint_mask(self, painter: QPainter) -> None:
        """Paint semi-transparent dark overlay, leaving selection area clear."""
        if self._selection_rect.isNull() or not self._selection_rect.isValid():
            # No selection — darken everything
            painter.fillRect(self.rect(), self.MASK_COLOR)
            return

        # Use clipping to paint the mask everywhere EXCEPT the selection
        full = QRegion(self.rect())
        selection = QRegion(self._selection_rect)
        mask_region = full.subtracted(selection)

        painter.setClipRegion(mask_region)
        painter.fillRect(self.rect(), self.MASK_COLOR)
        painter.setClipping(False)

    def _paint_selection(self, painter: QPainter) -> None:
        """Paint the selection rectangle border."""
        pen = QPen(self.SELECTION_BORDER, self.SELECTION_BORDER_WIDTH)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._selection_rect)

    def _paint_region_highlight(self, painter: QPainter, region: DetectRegion) -> None:
        """Paint a highlighted auto-detect region."""
        # Fill
        painter.fillRect(region.rect, self.HIGHLIGHT_COLOR)
        # Border
        pen = QPen(self.HIGHLIGHT_BORDER, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(region.rect)

    def _paint_dimensions(self, painter: QPainter) -> None:
        """Paint a WxH dimension label near the selection rectangle."""
        rect = self._selection_rect
        w, h = rect.width(), rect.height()
        label_text = f"{w} × {h}"

        font = QFont("monospace", 11)
        font.setBold(True)
        painter.setFont(font)

        # Measure text
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(label_text)
        padding = 6

        # Position: below the bottom-left corner of selection
        label_x = rect.left()
        label_y = rect.bottom() + 8

        # If label would go off-screen, put it above or inside
        if label_y + text_rect.height() + padding * 2 > self.height():
            label_y = rect.top() - text_rect.height() - padding * 2 - 4
        if label_y < 0:
            label_y = rect.top() + 4  # Inside, at top

        bg_rect = QRect(
            label_x,
            label_y,
            text_rect.width() + padding * 2,
            text_rect.height() + padding * 2,
        )

        # Background
        painter.fillRect(bg_rect, self.DIM_LABEL_BG)

        # Text
        painter.setPen(self.DIM_LABEL_FG)
        painter.drawText(
            bg_rect.left() + padding,
            bg_rect.top() + padding + fm.ascent(),
            label_text,
        )

    def _paint_crosshair(self, painter: QPainter) -> None:
        """Paint crosshair lines through the cursor position."""
        pen = QPen(self.CROSSHAIR_COLOR, 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        x, y = self._mouse_pos.x(), self._mouse_pos.y()

        # Horizontal line
        painter.drawLine(0, y, self.width(), y)
        # Vertical line
        painter.drawLine(x, 0, x, self.height())

    # --- Private logic methods ---

    def _find_region_at(self, x: int, y: int) -> DetectRegion | None:
        """Find the smallest auto-detect region containing the point.

        Regions are pre-sorted by area (smallest first), so the first
        match is the most specific (innermost) region — e.g., a button
        inside a panel inside a window.
        """
        for region in self._regions:
            if region.rect.contains(x, y):
                return region
        return None

    def _confirm_selection(self) -> None:
        """Emit the selected region and close."""
        if not self._selection_rect.isNull() and self._selection_rect.isValid():
            logger.info(
                "Region selected: %d,%d %dx%d",
                self._selection_rect.x(),
                self._selection_rect.y(),
                self._selection_rect.width(),
                self._selection_rect.height(),
            )
            self.region_selected.emit(self._selection_rect)
        self.close()

    def _cancel(self) -> None:
        """Cancel selection and close."""
        logger.info("Region selection cancelled")
        self._state = OverlayState.CANCELLED
        self.selection_cancelled.emit()
        self.close()
