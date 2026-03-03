from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QUndoCommand, QPainterPath, QLinearGradient, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QFormLayout, 
    QSpinBox, QPushButton, QComboBox, QDialogButtonBox, QLabel, QColorDialog
)

class CombineCommand(QUndoCommand):
    """Appends a second image to the current canvas either horizontally or vertically."""
    def __init__(self, editor, image2_path: str, config: dict) -> None:
        super().__init__("Combine Images")
        self.editor = editor
        
        self.old_pixmap = editor.image_item.pixmap()
        self.old_scene_rect = editor.scene.sceneRect()
        self.old_backdrop = editor.scene.backdrop_crop
        
        self.vector_items = []
        for item in editor.scene.items():
            if item != editor.image_item:
                self.vector_items.append(item)
                
        # 1. Rasterize current scene (Image 1)
        img1 = QImage(self.old_scene_rect.size().toSize(), QImage.Format.Format_ARGB32)
        img1.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img1)
        editor.scene.render(painter, QRectF(img1.rect()), self.old_scene_rect)
        painter.end()
        
        # 2. Load Image 2
        img2 = QImage(image2_path)
        if img2.isNull():
            raise ValueError(f"Failed to load image from {image2_path}")
            
        orientation = config.get('orientation', 'Horizontal')
        spacing = config.get('spacing', 0)
        alignment = config.get('alignment', 'Center')
        bg_color = config.get('bg_color', None)
            
        # 3. Calculate new dimensions and offsets
        if orientation == "Horizontal":
            total_w = img1.width() + img2.width() + spacing
            total_h = max(img1.height(), img2.height())
            
            y1, y2 = 0, 0
            if alignment == "Start (Top/Left)":
                pass
            elif alignment == "End (Bottom/Right)":
                y1 = total_h - img1.height()
                y2 = total_h - img2.height()
            else: # Center
                y1 = (total_h - img1.height()) // 2
                y2 = (total_h - img2.height()) // 2
                
            x1 = 0
            x2 = img1.width() + spacing
        else: # Vertical
            total_w = max(img1.width(), img2.width())
            total_h = img1.height() + img2.height() + spacing
            
            x1, x2 = 0, 0
            if alignment == "Start (Top/Left)":
                pass
            elif alignment == "End (Bottom/Right)":
                x1 = total_w - img1.width()
                x2 = total_w - img2.width()
            else: # Center
                x1 = (total_w - img1.width()) // 2
                x2 = (total_w - img2.width()) // 2
                
            y1 = 0
            y2 = img1.height() + spacing
            
        final_img = QImage(total_w, total_h, QImage.Format.Format_ARGB32)
        if bg_color and bg_color.isValid():
            final_img.fill(bg_color)
        else:
            final_img.fill(Qt.GlobalColor.transparent)
        
        p = QPainter(final_img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 4. Draw both images
        p.drawImage(x1, y1, img1)
        p.drawImage(x2, y2, img2)
            
        p.end()
        
        self.new_pixmap = QPixmap.fromImage(final_img)
        self.new_scene_rect = QRectF(0, 0, total_w, total_h)
        self.new_backdrop = final_img
        
    def redo(self) -> None:
        for item in self.vector_items:
            self.editor.scene.removeItem(item)
        self.editor.image_item.setPixmap(self.new_pixmap)
        self.editor.scene.setSceneRect(self.new_scene_rect)
        self.editor.scene.backdrop_crop = self.new_backdrop
        self.editor.view.fitInView(self.new_scene_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def undo(self) -> None:
        self.editor.image_item.setPixmap(self.old_pixmap)
        self.editor.scene.setSceneRect(self.old_scene_rect)
        self.editor.scene.backdrop_crop = self.old_backdrop
        for item in self.vector_items:
            if item.scene() is None:
                self.editor.scene.addItem(item)
        self.editor.view.fitInView(self.old_scene_rect, Qt.AspectRatioMode.KeepAspectRatio)


class BeautifyCommand(QUndoCommand):
    """Applies modern rounded corners, beautiful gradient background padding, and a soft shadow."""
    def __init__(self, editor, bg_style: str, padding: int, radius: int) -> None:
        super().__init__("Beautify Image")
        self.editor = editor
        
        self.old_pixmap = editor.image_item.pixmap()
        self.old_scene_rect = editor.scene.sceneRect()
        self.old_backdrop = editor.scene.backdrop_crop
        
        self.vector_items = []
        for item in editor.scene.items():
            if item != editor.image_item:
                self.vector_items.append(item)
                
        # 1. Rasterize current scene
        current_img = QImage(self.old_scene_rect.size().toSize(), QImage.Format.Format_ARGB32)
        current_img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(current_img)
        editor.scene.render(painter, QRectF(current_img.rect()), self.old_scene_rect)
        painter.end()
        
        # 2. Clip corners of the original image
        clipped_img = QImage(current_img.size(), QImage.Format.Format_ARGB32)
        clipped_img.fill(Qt.GlobalColor.transparent)
        
        clip_painter = QPainter(clipped_img)
        clip_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(current_img.rect()), radius, radius)
        clip_painter.setClipPath(path)
        clip_painter.drawImage(0, 0, current_img)
        clip_painter.end()
        
        # 3. Define the Drop Shadow bounds
        shadow_radius = min(40, max(15, int(min(current_img.width(), current_img.height()) * 0.05)))
        shadow_offset_y = int(shadow_radius * 0.6)
        
        # We need padding to at least fit the shadow
        actual_padding = max(padding, shadow_radius * 2)
        
        total_w = current_img.width() + (actual_padding * 2)
        total_h = current_img.height() + (actual_padding * 2)
        
        # 4. Generate the gradient background
        final_img = QImage(total_w, total_h, QImage.Format.Format_ARGB32)
        
        bg_painter = QPainter(final_img)
        bg_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if bg_style == "Transparent":
            final_img.fill(Qt.GlobalColor.transparent)
        else:
            gradient = QLinearGradient(0, 0, total_w, total_h)
            if bg_style == "Sunset":
                gradient.setColorAt(0.0, QColor("#ff7e5f"))
                gradient.setColorAt(1.0, QColor("#feb47b"))
            elif bg_style == "Ocean":
                gradient.setColorAt(0.0, QColor("#2b5876"))
                gradient.setColorAt(1.0, QColor("#4e4376"))
            elif bg_style == "Purple Pink":
                gradient.setColorAt(0.0, QColor("#a18cd1"))
                gradient.setColorAt(1.0, QColor("#fbc2eb"))
            elif bg_style == "Mojave":
                gradient.setColorAt(0.0, QColor("#ffd194"))
                gradient.setColorAt(1.0, QColor("#70e1f5"))
            elif bg_style == "Solid White":
                gradient.setColorAt(0.0, QColor(255, 255, 255))
                gradient.setColorAt(1.0, QColor(255, 255, 255))
            else: # Default dark
                gradient.setColorAt(0.0, QColor("#141e30"))
                gradient.setColorAt(1.0, QColor("#243b55"))
                
            bg_painter.fillRect(final_img.rect(), QBrush(gradient))
            
        bg_painter.end()
        
        # 5. Paint the clipped image with shadow onto the background using a temporary scene
        from PySide6.QtWidgets import QGraphicsScene, QGraphicsDropShadowEffect, QGraphicsPixmapItem
        
        temp_scene = QGraphicsScene()
        temp_scene.setSceneRect(0, 0, total_w, total_h)
        
        pixmap_item = temp_scene.addPixmap(QPixmap.fromImage(clipped_img))
        pixmap_item.setPos(actual_padding, actual_padding)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(shadow_radius)
        shadow.setOffset(0, shadow_offset_y)
        shadow.setColor(QColor(0, 0, 0, 140))
        pixmap_item.setGraphicsEffect(shadow)
        
        p = QPainter(final_img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        temp_scene.render(p)
        p.end()
        
        self.new_pixmap = QPixmap.fromImage(final_img)
        self.new_scene_rect = QRectF(0, 0, total_w, total_h)
        self.new_backdrop = final_img
        
    def redo(self) -> None:
        for item in self.vector_items:
            self.editor.scene.removeItem(item)
        self.editor.image_item.setPixmap(self.new_pixmap)
        self.editor.scene.setSceneRect(self.new_scene_rect)
        self.editor.scene.backdrop_crop = self.new_backdrop
        self.editor.view.fitInView(self.new_scene_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def undo(self) -> None:
        self.editor.image_item.setPixmap(self.old_pixmap)
        self.editor.scene.setSceneRect(self.old_scene_rect)
        self.editor.scene.backdrop_crop = self.old_backdrop
        for item in self.vector_items:
            if item.scene() is None:
                self.editor.scene.addItem(item)
        self.editor.view.fitInView(self.old_scene_rect, Qt.AspectRatioMode.KeepAspectRatio)


class BeautifyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Beautify Image")
        self.setMinimumWidth(300)
        
        layout = QFormLayout(self)
        
        self.bg_style = QComboBox()
        self.bg_style.addItems(["Sunset", "Ocean", "Purple Pink", "Mojave", "Solid White", "Dark Chrome", "Transparent"])
        self.bg_style.setCurrentText("Purple Pink")
        
        self.padding = QSpinBox()
        self.padding.setRange(20, 500)
        self.padding.setValue(60)
        self.padding.setSuffix(" px")
        
        self.radius = QSpinBox()
        self.radius.setRange(0, 100)
        self.radius.setValue(12)
        self.radius.setSuffix(" px")
        
        layout.addRow("Background Style:", self.bg_style)
        layout.addRow("Background Padding:", self.padding)
        layout.addRow("Window Corner Radius:", self.radius)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow("", buttons)

    def get_config(self) -> dict:
        return {
            'bg_style': self.bg_style.currentText(),
            'padding': self.padding.value(),
            'radius': self.radius.value()
        }


class CombineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Combine Images")
        self.setMinimumWidth(350)
        
        layout = QFormLayout(self)
        
        self.orientation = QComboBox()
        self.orientation.addItems(["Horizontal (Side-by-side)", "Vertical (Stacked)"])
        
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 500)
        self.spacing.setValue(20)
        self.spacing.setSuffix(" px")
        
        self.alignment = QComboBox()
        self.alignment.addItems(["Center", "Start (Top/Left)", "End (Bottom/Right)"])
        
        self.bg_color = QColor(255, 255, 255) # Default White
        self.btn_bg_color = QPushButton("Pick Fill Color (White)")
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        
        layout.addRow("Orientation:", self.orientation)
        layout.addRow("Orthogonal Alignment:", self.alignment)
        layout.addRow("Gap Spacing:", self.spacing)
        layout.addRow("Background Fill:", self.btn_bg_color)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow("", buttons)

    def _pick_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self, "Select Background Fill Color")
        if color.isValid():
            self.bg_color = color
            self.btn_bg_color.setText(f"Pick Fill Color ({color.name()})")

    def get_config(self) -> dict:
        orientation_val = "Horizontal" if "Horizontal" in self.orientation.currentText() else "Vertical"
        return {
            'orientation': orientation_val,
            'spacing': self.spacing.value(),
            'alignment': self.alignment.currentText(),
            'bg_color': self.bg_color
        }
