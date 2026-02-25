"""Standalone Image Editor for ShotX."""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QTimer, Signal, QPointF
from PySide6.QtGui import QImage, QPixmap, QPainter, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QGraphicsView, QGraphicsPixmapItem,
    QToolBar, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QApplication
)

from shotx.ui.annotations.scene import AnnotationScene, AnnotationTool
from shotx.ui.annotations.toolbar import AnnotationToolbar

class EditorGraphicsView(QGraphicsView):
    """Custom view to handle zooming and specific canvas interactions."""
    
    # Emitted when zoom percentage changes (e.g. 100 for 100%)
    zoom_changed = Signal(int)
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._space_pressed = False
        self._previous_drag_mode = self.dragMode()
        self._current_zoom = 100  # percentage
        
        # Performance/rendering hints
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)

    def set_zoom(self, zoom_level: int, anchor_point: QPointF | None = None) -> None:
        """Set the absolute zoom level as a percentage (10 to 500)."""
        # Clamp between 10% and 500%
        zoom_level = max(10, min(500, zoom_level))
        if zoom_level == self._current_zoom:
            return
            
        old_zoom = self._current_zoom
        self._current_zoom = zoom_level
        
        # Calculate the mathematical scale factor needed to go from exactly old_zoom to zoom_level
        scale_factor = self._current_zoom / old_zoom
        
        if anchor_point:
            # Map the viewport anchor to a scene coordinate *before* scaling
            scene_pos = self.mapToScene(anchor_point.toPoint())
            
            self.scale(scale_factor, scale_factor)
            
            # Map that same viewport anchor to a scene coordinate *after* scaling
            new_scene_pos = self.mapToScene(anchor_point.toPoint())
            
            # Translate the view so the scene coordinate stays under the anchor
            delta = new_scene_pos - scene_pos
            self.translate(delta.x(), delta.y())
        else:
            self.scale(scale_factor, scale_factor)
            
        self.zoom_changed.emit(self._current_zoom)

    def mousePressEvent(self, event) -> None:
        if self._space_pressed:
            # Force panning only, preventing clicking/moving items underneath
            self.setInteractive(False)
            super().mousePressEvent(event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        # Restore interactivity after drag finishes
        if self._space_pressed:
            self.setInteractive(True)
            event.accept()
        
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self._previous_drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            self.setDragMode(self._previous_drag_mode)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        # Standard Ctrl + Scroll to Zoom
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                # Zoom in: ~15% steps
                new_zoom = int(self._current_zoom * 1.15)
                # Snap to nice round numbers if close
                if 95 <= new_zoom <= 105: new_zoom = 100
                if 195 <= new_zoom <= 205: new_zoom = 200
            else:
                # Zoom out: ~15% steps
                new_zoom = int(self._current_zoom / 1.15)
                # Snap to nice round numbers if close
                if 95 <= new_zoom <= 105: new_zoom = 100
                if 195 <= new_zoom <= 205: new_zoom = 200
                
            self.set_zoom(new_zoom, anchor_point=event.position())
            event.accept()
        else:
            super().wheelEvent(event)

class ImageEditorWindow(QMainWindow):
    """Main window for the ShotX Image Editor."""

    def __init__(self, parent=None, initial_image: QImage | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ShotX — Image Editor")
        self.resize(1024, 768)
        
        # Setup Scene and View
        self.scene = AnnotationScene(self)
        self.view = EditorGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # Dark grid or gray background for the canvas
        self.view.setBackgroundBrush(Qt.GlobalColor.darkGray)
        
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        from PySide6.QtWidgets import QGridLayout
        layout = QGridLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_item: QGraphicsPixmapItem | None = None
        self.current_image_path: str | None = None
        
        self._setup_system_toolbar()
        
        # 1. Base layer is the view
        layout.addWidget(self.view, 0, 0)
        
        # 2. Setup Annotation Toolbar in overlay layout
        self._setup_annotation_toolbar(layout)
        
        # 3. Setup Zoom overlay UI
        self._setup_zoom_ui(layout)
        
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

    def _setup_annotation_toolbar(self, grid_layout) -> None:
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QVBoxLayout
        self.annotation_toolbar = AnnotationToolbar(initial_color=QColor(255, 0, 0), parent=self.centralWidget())
        
        # Wrapper to add padding from the top edge
        self.toolbar_container = QWidget(self.centralWidget())
        container_layout = QVBoxLayout(self.toolbar_container)
        container_layout.setContentsMargins(0, 16, 0, 0)
        container_layout.addWidget(self.annotation_toolbar)
        
        grid_layout.addWidget(
            self.toolbar_container, 
            0, 0, 
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        
        self.annotation_toolbar.tool_selected.connect(self._on_tool_selected)
        self.annotation_toolbar.undo_requested.connect(self.scene.undo_stack.undo)
        self.annotation_toolbar.redo_requested.connect(self.scene.undo_stack.redo)
        self.annotation_toolbar.color_changed.connect(lambda c: setattr(self.scene, 'current_color', c))
        self.annotation_toolbar.thickness_changed.connect(lambda t: setattr(self.scene, 'current_thickness', t))
        
        self.annotation_toolbar.cancel_requested.connect(self.close)

    def _setup_zoom_ui(self, grid_layout) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QLabel
        
        self.zoom_widget = QWidget(self.centralWidget())
        self.zoom_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 240);
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 16px;
                font-weight: bold;
                padding: 4px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
                border: none;
                padding: 0 8px;
            }
        """)
        
        layout = QHBoxLayout(self.zoom_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        btn_out = QPushButton("−")
        btn_out.setFixedSize(30, 30)
        btn_out.clicked.connect(lambda: self.view.set_zoom(int(self.view._current_zoom / 1.15)))
        layout.addWidget(btn_out)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(50)
        layout.addWidget(self.zoom_label)
        
        btn_in = QPushButton("+")
        btn_in.setFixedSize(30, 30)
        btn_in.clicked.connect(lambda: self.view.set_zoom(int(self.view._current_zoom * 1.15)))
        layout.addWidget(btn_in)
        
        # Wrapper to add padding from the bottom-right edges
        self.zoom_container = QWidget(self.centralWidget())
        container_layout = QHBoxLayout(self.zoom_container)
        container_layout.setContentsMargins(0, 0, 16, 16)
        container_layout.addWidget(self.zoom_widget)
        
        grid_layout.addWidget(
            self.zoom_container, 
            0, 0, 
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )
        
        # Connect view signal to label update
        self.view.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z}%"))

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
