"""UI component for displaying a generated QR code."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class QRDisplayOverlay(QWidget):
    """A floating window that displays a QR code."""

    def __init__(self, qr_image: QImage, text: str) -> None:
        super().__init__()
        self._qr_image = qr_image
        self._text = text

        # Set window flags for a splash-like, always-on-top window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Calculate size based on QR image + some padding
        padding = 40
        self.setFixedSize(
            self._qr_image.width() + padding,
            self._qr_image.height() + padding + 20 # Extra for text label if we want one
        )

        # Center on screen
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        painter.setBrush(QColor(30, 30, 30, 240))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

        # Draw QR image centered
        x = (self.width() - self._qr_image.width()) // 2
        y = 20 # Top padding
        painter.drawImage(x, y, self._qr_image)

        # Draw a little instruction
        painter.setPen(QColor(200, 200, 200))
        text_rect = QRect(0, self.height() - 30, self.width(), 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "Click to close")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
