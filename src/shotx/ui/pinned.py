"""UI component for pinning snippets to the screen with a persistent resize handle and notifications."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QRect, QSize, QPointF
from PySide6.QtGui import QPixmap, QCursor, QAction, QIcon, QMouseEvent, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QMenu, QFileDialog, QApplication

from shotx.ui.notification import notify_info, notify_error

logger = logging.getLogger(__name__)

class PinnedImageLabel(QLabel):
    """Custom label that draws a resize handle on top of the image."""
    
    HANDLE_SIZE = 10
    
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Position at the EXTREME bottom right corner
        handle_x = self.width() - self.HANDLE_SIZE
        handle_y = self.height() - self.HANDLE_SIZE
        
        painter.setPen(QPen(QColor(0, 0, 0, 200), 1.5))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(handle_x - 1, handle_y - 1, self.HANDLE_SIZE, self.HANDLE_SIZE)

class PinnedWidget(QWidget):
    """
    A frameless, always-on-top widget that displays a pinned image snippet.
    Supports dragging and bottom-right proportional resizing with a visual handle.
    """

    MIN_SIZE_PX = 40
    MIN_SIZE_RATIO = 0.25  # 25% of original
    MAX_SCREEN_RATIO = 0.8  # 80% of screen
    SENSITIVITY = 30  # Increased sensitivity for handle

    def __init__(self, pixmap: QPixmap, parent=None) -> None:
        super().__init__(parent)
        self.pixmap = pixmap
        self.original_size = pixmap.size()
        self.aspect_ratio = pixmap.width() / pixmap.height()
        
        # Get screen constraints
        screen = QApplication.primaryScreen().geometry()
        self.max_w = int(screen.width() * self.MAX_SCREEN_RATIO)
        self.max_h = int(screen.height() * self.MAX_SCREEN_RATIO)
        
        # Calculate min size based on 25% of original
        self.min_w = max(self.MIN_SIZE_PX, int(self.original_size.width() * self.MIN_SIZE_RATIO))
        self.min_h = int(self.min_w / self.aspect_ratio)
        
        # Explicitly allow the widget to shrink by overriding the default MinimumSizeHint
        self.setMinimumSize(self.min_w, self.min_h)
        
        # Window Flags: Frameless, Always on Top, Tool window (no taskbar entry)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # UI Setup
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = PinnedImageLabel()
        self.label.setPixmap(pixmap)
        self.label.setScaledContents(True)
        # Prevent the label from enforcing the original pixmap size as its minimum
        self.label.setMinimumSize(self.min_w, self.min_h)
        
        # Subtle 1px border for "Premium" look
        self.label.setStyleSheet("""
            QLabel {
                border: 1px solid rgba(128, 128, 128, 0.4);
                background-color: transparent;
            }
        """)
        
        self.layout.addWidget(self.label)
        
        # State
        self.setMouseTracking(True)
        self._resizing = False
        self._moving = False
        
        # Starting Position
        cursor_pos = QCursor.pos()
        self.resize(pixmap.size())
        self.move(cursor_pos.x() - pixmap.width() // 2, cursor_pos.y() - pixmap.height() // 2)

    def _is_over_handle(self, pos: QPoint) -> bool:
        """Check if mouse is over the bottom-right resize corner."""
        return (pos.x() >= self.width() - self.SENSITIVITY and 
                pos.y() >= self.height() - self.SENSITIVITY)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_over_handle(event.pos()):
                self._resizing = True
                self._resize_start_pos = event.globalPosition()
                self._resize_start_geo = self.geometry()
                event.accept()
            else:
                # We DON'T start move here to keep double-click detection alive
                self._moving = True
                event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Cursor feedback
        if self._is_over_handle(event.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # Proportional Resizing Logic
        if self._resizing:
            delta = event.globalPosition() - self._resize_start_pos
            
            # Use dx as primary driver
            new_w = self._resize_start_geo.width() + int(delta.x())
            
            # Clamp width
            new_w = max(self.min_w, min(new_w, self.max_w))
            new_h = int(new_w / self.aspect_ratio)
            
            # Clamp height and re-adjust width if needed
            if new_h > self.max_h:
                new_h = self.max_h
                new_w = int(new_h * self.aspect_ratio)
            elif new_h < self.min_h:
                new_h = self.min_h
                new_w = int(new_h * self.aspect_ratio)

            self.resize(new_w, new_h)
            event.accept()
        elif self._moving and event.buttons() & Qt.MouseButton.LeftButton:
            # We started moving, hand off to system
            self._moving = False
            self.windowHandle().startSystemMove()
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._resizing = False
        self._moving = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # We explicitly accept the event so the window closes properly
            event.accept()
            self.close()

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2e3440; color: #eceff4; border: 1px solid #434c5e; padding: 5px; }
            QMenu::item:selected { background-color: #4c566a; border-radius: 3px; }
        """)

        copy_action = QAction("📋 Copy to Clipboard", self)
        copy_action.triggered.connect(self._on_copy)
        
        save_action = QAction("💾 Save to File...", self)
        save_action.triggered.connect(self._on_save)
        
        close_action = QAction("❌ Close (Double-click)", self)
        close_action.triggered.connect(self.close)
        
        menu.addAction(copy_action)
        menu.addAction(save_action)
        menu.addSeparator()
        menu.addAction(close_action)
        
        menu.exec(pos)

    def _on_copy(self) -> None:
        QApplication.clipboard().setPixmap(self.pixmap)
        notify_info(None, "Copied to Clipboard", "Pinned snippet image copied successfully.")

    def _on_save(self) -> None:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"pinned_{timestamp}.png"
        default_path = str(Path.home() / "Pictures" / default_name)
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Pinned Snippet", default_path, 
            "Images (*.png *.jpg *.webp)"
        )
        
        if path:
            success = self.pixmap.save(path)
            if success:
                notify_info(None, "Saved Successfully", f"Pinned snippet saved to:\n{path}", file_path=path)
            else:
                notify_error(None, f"Save failed: Could not write to {path}")
