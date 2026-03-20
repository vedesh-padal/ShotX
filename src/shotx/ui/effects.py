from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QUndoCommand
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QGraphicsScene,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class EffectsCommand(QUndoCommand):
    """Applies borders, padding, shadows, and watermarks to the image, flattening vectors."""

    def __init__(self, editor, config: dict) -> None:
        super().__init__("Apply Image Effects")
        self.editor = editor
        self.config = config

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

        bw = config.get('border_width', 0)
        pad = config.get('padding', 0)
        has_shadow = config.get('shadow_enabled', False)
        sr = config.get('shadow_radius', 15) if has_shadow else 0
        sx = config.get('shadow_offset_x', 0) if has_shadow else 0
        sy = config.get('shadow_offset_y', 10) if has_shadow else 0

        # Draw Border directly onto the current image by expanding it slightly
        if bw > 0:
            bordered = QImage(current_img.width() + bw*2, current_img.height() + bw*2, QImage.Format.Format_ARGB32)
            bordered.fill(config.get('border_color', Qt.GlobalColor.black))
            bp = QPainter(bordered)
            bp.drawImage(bw, bw, current_img)
            bp.end()
            current_img = bordered

        shadow_pad_l = shadow_pad_r = shadow_pad_t = shadow_pad_b = 0
        if has_shadow:
            shadow_pad_l = sr - min(0, sx)
            shadow_pad_r = sr + max(0, sx)
            shadow_pad_t = sr - min(0, sy)
            shadow_pad_b = sr + max(0, sy)

        total_w = current_img.width() + (pad * 2) + shadow_pad_l + shadow_pad_r
        total_h = current_img.height() + (pad * 2) + shadow_pad_t + shadow_pad_b

        final_img = QImage(total_w, total_h, QImage.Format.Format_ARGB32)
        if config.get('bg_color'):
            final_img.fill(config['bg_color'])
        else:
            final_img.fill(Qt.GlobalColor.transparent)

        offset_x = pad + shadow_pad_l
        offset_y = pad + shadow_pad_t

        if has_shadow:
            # Drop shadow requires QGraphicsScene to render natively
            temp_scene = QGraphicsScene()
            temp_scene.setSceneRect(0, 0, total_w, total_h)

            # bg optionally drawn to final_img already
            pixmap_item = temp_scene.addPixmap(QPixmap.fromImage(current_img))
            pixmap_item.setPos(offset_x, offset_y)

            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(sr)
            shadow.setOffset(sx, sy)
            shadow.setColor(QColor(0, 0, 0, 180))
            pixmap_item.setGraphicsEffect(shadow)

            p = QPainter(final_img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            temp_scene.render(p)
        else:
            p = QPainter(final_img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.drawImage(offset_x, offset_y, current_img)

        # Draw Watermark
        wm_text = config.get('watermark_text', "")
        if wm_text:
            opacity = config.get('watermark_opacity', 0.3)
            pos_mode = config.get('watermark_pos', "Bottom Right")

            p.setOpacity(opacity)
            font = QFont("sans-serif", int(total_w * 0.03))
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(255, 255, 255))

            # Add subtle dark text drop shadow for visibility
            shadow_pen = QColor(0, 0, 0)

            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(wm_text)
            th = fm.height()

            m = 20 # margin
            if pos_mode == "Bottom Right":
                tx = total_w - tw - m
                ty = total_h - m
            elif pos_mode == "Bottom Left":
                tx = m
                ty = total_h - m
            elif pos_mode == "Top Right":
                tx = total_w - tw - m
                ty = m + th
            elif pos_mode == "Top Left":
                tx = m
                ty = m + th
            elif pos_mode == "Tiled Grid":
                # Draw repeatedly across the image
                step_x = tw + 50
                step_y = th + 50
                for yg in range(m + th, total_h, step_y):
                    for xg in range(m, total_w, step_x):
                        p.setPen(shadow_pen)
                        p.drawText(int(xg+1), int(yg+1), wm_text)
                        p.setPen(QColor(255, 255, 255))
                        p.drawText(int(xg), int(yg), wm_text)
                tx, ty = -1000, -1000 # Hide the single text draw step below
            else: # Center
                tx = (total_w / 2) - (tw / 2)
                ty = (total_h / 2) + (th / 2)

            p.setPen(shadow_pen)
            p.drawText(int(tx+2), int(ty+2), wm_text)
            p.setPen(QColor(255, 255, 255))
            p.drawText(int(tx), int(ty), wm_text)

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


class EffectsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Effects")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)

        # --- Border & Padding Tab ---
        border_tab = QWidget()
        border_layout = QFormLayout(border_tab)

        self.border_width = QSpinBox()
        self.border_width.setRange(0, 100)
        self.border_width.setValue(0)
        self.border_color = QColor(0, 0, 0)
        self.btn_border_color = QPushButton("Pick Color (Black)")
        self.btn_border_color.clicked.connect(self._pick_border_color)

        self.padding = QSpinBox()
        self.padding.setRange(0, 500)
        self.padding.setValue(0)
        self.bg_color = QColor(255, 255, 255)
        self.btn_bg_color = QPushButton("Pick Color (White)")
        self.btn_bg_color.clicked.connect(self._pick_bg_color)

        self.shadow_cb = QCheckBox("Enable Drop Shadow")
        self.shadow_radius = QSpinBox()
        self.shadow_radius.setRange(1, 100)
        self.shadow_radius.setValue(15)
        self.shadow_dx = QSpinBox()
        self.shadow_dx.setRange(-100, 100)
        self.shadow_dx.setValue(0)
        self.shadow_dy = QSpinBox()
        self.shadow_dy.setRange(-100, 100)
        self.shadow_dy.setValue(10)

        border_layout.addRow("Border Width (px):", self.border_width)
        border_layout.addRow("Border Color:", self.btn_border_color)
        border_layout.addRow("Background Padding (px):", self.padding)
        border_layout.addRow("Background Color:", self.btn_bg_color)
        border_layout.addRow(QLabel("<hr>"))
        border_layout.addRow(self.shadow_cb)
        border_layout.addRow("Shadow Blur Radius:", self.shadow_radius)
        border_layout.addRow("Shadow Offset X:", self.shadow_dx)
        border_layout.addRow("Shadow Offset Y:", self.shadow_dy)

        self.tabs.addTab(border_tab, "Border & Shadow")

        # --- Watermark Tab ---
        watermark_tab = QWidget()
        wm_layout = QFormLayout(watermark_tab)

        self.wm_text = QLineEdit()
        self.wm_text.setPlaceholderText("e.g. shotx.app")

        self.wm_opacity = QDoubleSpinBox()
        self.wm_opacity.setRange(0.01, 1.0)
        self.wm_opacity.setSingleStep(0.1)
        self.wm_opacity.setValue(0.3)

        self.wm_pos = QComboBox()
        self.wm_pos.addItems(["Bottom Right", "Bottom Left", "Top Right", "Top Left", "Center", "Tiled Grid"])

        wm_layout.addRow("Text:", self.wm_text)
        wm_layout.addRow("Opacity (0.0 - 1.0):", self.wm_opacity)
        wm_layout.addRow("Position:", self.wm_pos)

        self.tabs.addTab(watermark_tab, "Watermark")

        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_border_color(self):
        color = QColorDialog.getColor(self.border_color, self, "Select Border Color")
        if color.isValid():
            self.border_color = color
            self.btn_border_color.setText(f"Pick Color ({color.name()})")

    def _pick_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self, "Select Background Color")
        if color.isValid():
            self.bg_color = color
            self.btn_bg_color.setText(f"Pick Color ({color.name()})")

    def get_config(self) -> dict:
        return {
            'border_width': self.border_width.value(),
            'border_color': self.border_color,
            'padding': self.padding.value(),
            'bg_color': self.bg_color,
            'shadow_enabled': self.shadow_cb.isChecked(),
            'shadow_radius': self.shadow_radius.value(),
            'shadow_offset_x': self.shadow_dx.value(),
            'shadow_offset_y': self.shadow_dy.value(),
            'watermark_text': self.wm_text.text(),
            'watermark_opacity': self.wm_opacity.value(),
            'watermark_pos': self.wm_pos.currentText()
        }
