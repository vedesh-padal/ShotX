"""Standalone Image Editor for ShotX."""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QGraphicsView, QGraphicsPixmapItem,
    QToolBar, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QApplication
)

from shotx.ui.annotations.scene import AnnotationScene, AnnotationTool
from shotx.ui.annotations.toolbar import AnnotationToolbar

class ImageEditorWindow(QMainWindow):
    """Main window for the ShotX Image Editor."""

    def __init__(self, parent=None, initial_image: QImage | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ShotX — Image Editor")
        self.resize(1024, 768)
        
        # Setup Scene and View
        self.scene = AnnotationScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # Dark grid or gray background for the canvas
        self.view.setBackgroundBrush(Qt.GlobalColor.darkGray)
        
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        
        self.image_item: QGraphicsPixmapItem | None = None
        self.current_image_path: str | None = None
        
        self._setup_system_toolbar()
        
        # Add the floating annotation tools
        self._setup_annotation_toolbar()
        layout.addWidget(self.annotation_toolbar, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.view)
        
        # Setup global application shortcuts
        self._setup_shortcuts()
        
        # Apply dark theme specific to editor to match other UIs
        self._apply_theme()
        
        if initial_image and not initial_image.isNull():
            self.load_image_from_data(initial_image)

    def _setup_system_toolbar(self) -> None:
        self.system_toolbar = QToolBar("System", self)
        self.system_toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.system_toolbar)
        
        action_open = self.system_toolbar.addAction("📁 Open")
        action_open.triggered.connect(self._on_open_file)
        
        action_paste = self.system_toolbar.addAction("📋 Paste")
        action_paste.triggered.connect(self._on_paste_clipboard)
        
        self.action_save = self.system_toolbar.addAction("💾 Save As...")
        self.action_save.triggered.connect(self._on_save_as)
        
        self.system_toolbar.addSeparator()
        
        self.action_copy = self.system_toolbar.addAction("📄 Copy to Clipboard")
        self.action_copy.triggered.connect(self._on_copy_to_clipboard)

    def _setup_shortcuts(self) -> None:
        """Register keyboard shortcuts for the editor."""
        # Undo / Redo
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.scene.undo_stack.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.scene.undo_stack.redo)
        
        # Copy / Paste
        # We also support Ctrl+Shift+C just in case, though standard Ctrl+C works fine
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._on_copy_to_clipboard)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._on_copy_to_clipboard)
        
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self._on_paste_clipboard)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_as)

    def _setup_annotation_toolbar(self) -> None:
        from PySide6.QtGui import QColor
        self.annotation_toolbar = AnnotationToolbar(initial_color=QColor(255, 0, 0), parent=self.centralWidget())
        
        self.annotation_toolbar.tool_selected.connect(self._on_tool_selected)
        self.annotation_toolbar.undo_requested.connect(self.scene.undo_stack.undo)
        self.annotation_toolbar.redo_requested.connect(self.scene.undo_stack.redo)
        self.annotation_toolbar.color_changed.connect(lambda c: setattr(self.scene, 'current_color', c))
        self.annotation_toolbar.thickness_changed.connect(lambda t: setattr(self.scene, 'current_thickness', t))
        
        # We don't need Accept/Cancel in a standalone editor window
        # but we can wire Cancel to just close the window
        self.annotation_toolbar.cancel_requested.connect(self.close)
        


    def _on_tool_selected(self, tool: AnnotationTool) -> None:
        self.scene.current_tool = tool
        # Allow panning canvas when SELECT tool is active
        if tool == AnnotationTool.SELECT:
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _apply_theme(self) -> None:
        """Apply a modern dark theme to the Image Editor."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2e3440;
            }
            QToolBar {
                background-color: #3b4252;
                border-bottom: 1px solid #434c5e;
            }
            QToolButton {
                color: #eceff4;
                padding: 6px;
                border-radius: 4px;
                font-weight: 500;
            }
            QToolButton:hover {
                background-color: #4c566a;
            }
        """)

    def load_image_from_file(self, path: str) -> None:
        image = QImage(path)
        if image.isNull():
            QMessageBox.critical(self, "Error", f"Failed to load image from\n{path}")
            return
        self.current_image_path = path
        self.load_image_from_data(image)

    def load_image_from_data(self, image: QImage) -> None:
        self.scene.clear()
        pixmap = QPixmap.fromImage(image)
        self.image_item = self.scene.addPixmap(pixmap)
        
        # Ensure the scene rect exactly matches the image size
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        
        # Set backdrop crop into scene so blur tool works
        self.scene.backdrop_crop = image
        
        # Center the image in the view and scale it down if it's too big
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.load_image_from_file(file_path)

    def _on_paste_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if not image.isNull():
            self.load_image_from_data(image)
        else:
            QMessageBox.warning(self, "No Image", "The clipboard does not contain a valid image.")

    def _on_save_as(self) -> None:
        if not self.image_item:
            return
        
        default_path = self.current_image_path or "edited_image.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", default_path, "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            # Render the scene to an image
            rect = self.scene.sceneRect().toRect()
            image = QImage(rect.size(), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(image)
            self.scene.render(painter)
            painter.end()
            
            if image.save(file_path):
                self.current_image_path = file_path
                # Visual feedback: Change text to "Saved!" for 1.5 seconds
                original_text = self.action_save.text()
                self.action_save.setText("✅ Saved!")
                QTimer.singleShot(1500, lambda: self.action_save.setText(original_text))
            else:
                QMessageBox.critical(self, "Error", "Failed to save image.")

    def _on_copy_to_clipboard(self) -> None:
        if not self.image_item:
            return
            
        rect = self.scene.sceneRect().toRect()
        image = QImage(rect.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(image)
        self.scene.render(painter)
        painter.end()
        
        QApplication.clipboard().setImage(image)
        
        # Visual feedback: Change text to "Copied!" for 1.5 seconds
        original_text = self.action_copy.text()
        self.action_copy.setText("✅ Copied!")
        QTimer.singleShot(1500, lambda: self.action_copy.setText(original_text))
