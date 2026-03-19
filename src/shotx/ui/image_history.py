"""Image History — thumbnail grid view for ShotX.

Renders past captures as a responsive grid of clickable thumbnails,
mirroring the ShareX "Image History" view.  This widget is embedded
in the center of the Main Window.

The grid uses ``QListWidget`` in ``IconMode`` with background
``ThumbnailWorker`` threads for lazy-loading, ensuring smooth scrolling
even for large histories.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRunnable, QObject, Signal, Slot, QThreadPool
from PySide6.QtGui import QIcon, QAction, QPixmap, QImageReader, QImage
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QMessageBox,
    QAbstractItemView,
)

from shotx.output.clipboard import copy_text_to_clipboard

logger = logging.getLogger(__name__)

_THUMB_SIZE = QSize(160, 120)


# ---------------------------------------------------------------------------
# Background thumbnail worker (reuses the same pattern as history.py)
# ---------------------------------------------------------------------------

class _GridThumbnailSignals(QObject):
    finished = Signal(int, QImage)  # db_record_id, decoded_image


class _GridThumbnailWorker(QRunnable):
    """Decode an image file into a thumbnail on a background thread."""

    def __init__(self, record_id: int, filepath: str):
        super().__init__()
        self.record_id = record_id
        self.filepath = filepath
        self.signals = _GridThumbnailSignals()

    @Slot()
    def run(self):
        reader = QImageReader(self.filepath)
        reader.setScaledSize(_THUMB_SIZE)
        img = reader.read()
        self.signals.finished.emit(self.record_id, img)


# ---------------------------------------------------------------------------
# ImageHistoryWidget — embeddable thumbnail grid
# ---------------------------------------------------------------------------

class ImageHistoryWidget(QWidget):
    """Visual thumbnail grid of past captures.

    Design decisions
    ~~~~~~~~~~~~~~~~
    * ``QListWidget`` in ``IconMode`` with ``Adjust`` resize mode gives us
      a CSS-Grid-like fluid layout that reflows on window resize.
    * Each ``QListWidgetItem`` stores the DB record id, filepath, and url
      in ``Qt.ItemDataRole.UserRole`` slots, following the same convention
      used throughout the codebase (see HistoryWidget).
    * Thumbnails are loaded via a background ``QRunnable`` to avoid blocking
      the main thread when hundreds of captures exist.
    * Context menus dynamically disable actions when the physical file or
      uploaded URL is unavailable, matching ShareX behaviour.
    """

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app = app_controller
        self._history_manager = self._app._history_manager

        self._thread_pool = QThreadPool.globalInstance()
        self._items_per_page = 60
        self._current_offset = 0
        self._is_loading = False
        self._all_loaded = False

        # Map record_id → QListWidgetItem for async thumbnail callbacks
        self._item_map: dict[int, QListWidgetItem] = {}

        self._setup_ui()
        self._load_data(clear=True)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Grid
        self._grid = QListWidget()
        self._grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setIconSize(_THUMB_SIZE)
        self._grid.setGridSize(QSize(_THUMB_SIZE.width() + 20, _THUMB_SIZE.height() + 40))
        self._grid.setMovement(QListWidget.Movement.Static)
        self._grid.setWrapping(True)
        self._grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._grid.setWordWrap(True)
        self._grid.setSpacing(4)
        self._grid.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._grid.setFlow(QListWidget.Flow.LeftToRight)
        # Eliminate internal viewport padding to keep grid edge-to-edge
        self._grid.setStyleSheet("QListWidget { padding: 0px; }")

        # Context menu
        self._grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid.customContextMenuRequested.connect(self._on_context_menu)
        self._grid.doubleClicked.connect(self._on_double_click)

        # Infinite scroll
        self._grid.verticalScrollBar().valueChanged.connect(self._on_scroll)

        layout.addWidget(self._grid)

        # Live-refresh when a new capture is completed
        from shotx.core.events import event_bus
        event_bus.capture_completed.connect(lambda f, s, t: self._load_data(clear=True))

    # ------------------------------------------------------------------
    # Data loading (paginated, async thumbnails)
    # ------------------------------------------------------------------

    def _on_scroll(self, value: int) -> None:
        if self._is_loading or self._all_loaded:
            return
        scrollbar = self._grid.verticalScrollBar()
        if value >= scrollbar.maximum() * 0.8:
            self._load_data(clear=False)

    def _load_data(self, clear: bool = False) -> None:
        if self._is_loading:
            return
        self._is_loading = True

        if clear:
            self._grid.clear()
            self._item_map.clear()
            self._current_offset = 0
            self._all_loaded = False

        if self._all_loaded:
            self._is_loading = False
            return

        records = self._history_manager.get_all(
            limit=self._items_per_page, offset=self._current_offset
        )

        if not records:
            self._all_loaded = True
            self._is_loading = False
            return

        for rec in records:
            full_name = Path(rec.filepath).name
            # Show a compact label: strip the "ShotX_" prefix and extension
            # so the date/time is visible without truncation
            stem = Path(rec.filepath).stem
            if stem.startswith("ShotX_"):
                display_name = stem[6:]  # e.g. "2026-03-19_20-53-03"
            else:
                display_name = stem

            item = QListWidgetItem()
            item.setText(display_name)
            item.setToolTip(
                f"{full_name}\n"
                f"{rec.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{rec.filepath}"
            )
            item.setIcon(QIcon.fromTheme("image-loading"))
            item.setSizeHint(QSize(_THUMB_SIZE.width() + 20, _THUMB_SIZE.height() + 40))

            # Store metadata in UserRole slots (same convention as HistoryWidget)
            item.setData(Qt.ItemDataRole.UserRole, rec.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, rec.filepath)
            item.setData(Qt.ItemDataRole.UserRole + 2, rec.url)

            self._grid.addItem(item)
            self._item_map[rec.id] = item

            # Dispatch background thumbnail decode
            worker = _GridThumbnailWorker(rec.id, rec.filepath)
            worker.signals.finished.connect(self._on_thumbnail_ready)
            self._thread_pool.start(worker)

        self._current_offset += len(records)
        self._is_loading = False

        if len(records) < self._items_per_page:
            self._all_loaded = True

    @Slot(int, QImage)
    def _on_thumbnail_ready(self, record_id: int, img: QImage) -> None:
        """Main-thread callback: set the decoded thumbnail on the grid item."""
        item = self._item_map.get(record_id)
        if not item:
            return
        if img.isNull():
            item.setIcon(QIcon.fromTheme("image-missing"))
        else:
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _get_selected_record(self) -> tuple[int, str, str | None] | None:
        items = self._grid.selectedItems()
        if not items:
            return None
        item = items[0]
        return (
            item.data(Qt.ItemDataRole.UserRole),
            item.data(Qt.ItemDataRole.UserRole + 1),
            item.data(Qt.ItemDataRole.UserRole + 2),
        )

    # ------------------------------------------------------------------
    # Context menu (visual-action focused, per ShareX Image History)
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        record = self._get_selected_record()
        if not record:
            return

        rec_id, filepath, url = record
        file_exists = Path(filepath).exists()
        has_url = bool(url)

        menu = QMenu(self)

        # Open
        a_open = menu.addAction("📂 Open")
        a_open.setEnabled(file_exists)
        a_open.triggered.connect(lambda: self._open_file(filepath))

        # Copy image to clipboard
        a_copy = menu.addAction("📋 Copy")
        a_copy.setEnabled(file_exists)
        a_copy.triggered.connect(lambda: self._copy_image(filepath))

        menu.addSeparator()

        # Upload
        a_upload = menu.addAction("☁️ Upload")
        a_upload.setEnabled(file_exists)
        a_upload.triggered.connect(lambda: self._upload_image(filepath))

        # Edit
        a_edit = menu.addAction("🖌️ Edit image...")
        a_edit.setEnabled(file_exists)
        a_edit.triggered.connect(lambda: self._edit_image(filepath))

        # Pin to screen
        a_pin = menu.addAction("📌 Pin to screen")
        a_pin.setEnabled(file_exists)
        a_pin.triggered.connect(lambda: self._pin_image(filepath))

        menu.addSeparator()

        # Remove from list (DB only)
        a_remove = menu.addAction("📤 Remove task from list")
        a_remove.triggered.connect(lambda: self._delete_record(rec_id))

        # Delete file locally
        a_delete = menu.addAction("🗑️ Delete file locally...")
        a_delete.setEnabled(file_exists)
        a_delete.triggered.connect(lambda: self._delete_file(rec_id, filepath))

        menu.addSeparator()

        # Shorten URL
        a_shorten = menu.addAction("🔗 Shorten URL")
        a_shorten.setEnabled(has_url)
        a_shorten.triggered.connect(lambda: self._shorten_url(url))

        menu.addSeparator()

        # Show QR code
        a_qr = menu.addAction("📱 Show QR code...")
        a_qr.setEnabled(file_exists)
        a_qr.triggered.connect(lambda: self._show_qr(filepath))

        # OCR image
        a_ocr = menu.addAction("📝 OCR image...")
        a_ocr.setEnabled(file_exists)
        a_ocr.triggered.connect(lambda: self._ocr_image(filepath))

        menu.exec(self._grid.viewport().mapToGlobal(pos))

    def _on_double_click(self, index) -> None:
        record = self._get_selected_record()
        if record:
            self._open_file(record[1])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_file(self, filepath: str) -> None:
        if Path(filepath).exists():
            from shotx.core.xdg import open_file
            open_file(filepath)
        else:
            QMessageBox.warning(
                self, "File Not Found",
                f"The file no longer exists:\n{filepath}",
            )

    def _copy_image(self, filepath: str) -> None:
        from shotx.output.clipboard import copy_image_to_clipboard
        img = QImage(filepath)
        if not img.isNull():
            copy_image_to_clipboard(img)
        else:
            QMessageBox.warning(
                self, "Warning",
                f"Could not load image to copy:\n{filepath}",
            )

    def _edit_image(self, filepath: str) -> None:
        from shotx.core.events import event_bus
        event_bus.tool_requested_with_args.emit(
            "editor", {"initial_image_path": filepath}
        )

    def _pin_image(self, filepath: str) -> None:
        from shotx.core.events import event_bus
        # pin_region is dispatched via capture_requested in CaptureController
        event_bus.capture_requested.emit("pin_region")

    def _upload_image(self, filepath: str) -> None:
        if Path(filepath).exists():
            from shotx.core.events import event_bus
            event_bus.upload_requested.emit(filepath)
        else:
            QMessageBox.warning(
                self, "File Not Found",
                f"Cannot upload missing file:\n{filepath}",
            )

    def _shorten_url(self, url: str) -> None:
        """Shorten the uploaded URL via the configured provider."""
        # Copy URL to clipboard first, then invoke the shortener which
        # reads from clipboard by default.
        copy_text_to_clipboard(url)
        self._app.shorten_clipboard_url()

    def _show_qr(self, filepath: str) -> None:
        """Generate a QR code from the file URL or path."""
        copy_text_to_clipboard(filepath)
        from shotx.core.events import event_bus
        event_bus.capture_requested.emit("qr_generate")

    def _ocr_image(self, filepath: str) -> None:
        """Run OCR on the selected image and copy result to clipboard."""
        try:
            from shotx.tools.ocr import extract_text_from_image
            text = extract_text_from_image(filepath)
            if text and text.strip():
                copy_text_to_clipboard(text.strip())
                from shotx.core.events import event_bus
                event_bus.notify_info_requested.emit(
                    "OCR Complete",
                    f"Extracted text copied to clipboard ({len(text.strip())} chars)",
                )
            else:
                from shotx.core.events import event_bus
                event_bus.notify_error_requested.emit(
                    "OCR found no text in the selected image."
                )
        except Exception as e:
            logger.error("OCR failed: %s", e)
            from shotx.core.events import event_bus
            event_bus.notify_error_requested.emit(f"OCR failed: {e}")

    def _delete_record(self, rec_id: int) -> None:
        self._history_manager.delete_record(rec_id)
        self._load_data(clear=True)

    def _delete_file(self, rec_id: int, filepath: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete File",
            f"Are you sure you want to permanently delete this file?\n\n{filepath}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            f = Path(filepath)
            if f.exists():
                f.unlink()
            self._history_manager.delete_record(rec_id)
            self._load_data(clear=True)

    def _on_clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all history records?\n\n"
            "(This will not delete the actual image files from your computer)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history_manager.clear_all()
            self._load_data(clear=True)
