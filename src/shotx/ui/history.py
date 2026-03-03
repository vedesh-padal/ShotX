"""History Viewer UI for ShotX.

Displays a tabulated view of past captures loaded from the SQLite database.

HistoryWidget is the embeddable QWidget used inside the Main Window.
HistoryDialog is a thin QDialog wrapper for standalone / CLI usage.
"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess

from PySide6.QtCore import Qt, QSize, QRunnable, QObject, Signal, Slot, QThreadPool
from PySide6.QtGui import QIcon, QAction, QPixmap, QImageReader, QImage
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)

from shotx.output.clipboard import copy_text_to_clipboard

logger = logging.getLogger(__name__)


class ThumbnailSignals(QObject):
    """Signals for the background thumbnail worker."""
    finished = Signal(int, QImage)  # row_number, generated_image


class ThumbnailWorker(QRunnable):
    """Background worker that decodes images into tiny thumbnails using minimal RAM."""

    def __init__(self, row: int, filepath: str):
        super().__init__()
        self.row = row
        self.filepath = filepath
        self.signals = ThumbnailSignals()

    @Slot()
    def run(self):
        # QImageReader decodes only the bytes needed for the target size,
        # never loading the full 4K frame into RAM.
        reader = QImageReader(self.filepath)
        reader.setScaledSize(QSize(100, 70))
        img = reader.read()
        # Emit raw QImage — QPixmap/QIcon require the main GUI thread.
        self.signals.finished.emit(self.row, img)


# ---------------------------------------------------------------------------
# HistoryWidget — embeddable QWidget (used inside MainWindow center panel)
# ---------------------------------------------------------------------------

class HistoryWidget(QWidget):
    """Embeddable history viewer widget with async thumbnails and infinite scroll."""

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app = app_controller
        self._history_manager = self._app._history_manager

        self._thread_pool = QThreadPool.globalInstance()
        self._items_per_page = 50
        self._current_offset = 0
        self._is_loading = False
        self._all_loaded = False

        self._setup_ui()
        self._load_data(clear=True)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tools bar
        tools_layout = QHBoxLayout()

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(lambda: self._load_data(clear=True))
        tools_layout.addWidget(self.btn_refresh)

        self.btn_clear = QPushButton("🗑️ Clear History")
        self.btn_clear.clicked.connect(self._on_clear_history)
        tools_layout.addWidget(self.btn_clear)

        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Preview", "Filename", "Time", "Size", "URL"
        ])

        # Table configurations
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        # Sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 250)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.table.verticalHeader().setDefaultSectionSize(80)

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(self._on_double_click)

        # Infinite scroll
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)

        layout.addWidget(self.table)

    # -- Formatting helpers --------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable string."""
        if size_bytes == 0:
            return "0 B"
        sizes = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(sizes) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {sizes[i]}"

    # -- Data loading --------------------------------------------------------

    def _on_scroll(self, value: int) -> None:
        """Trigger next page load when scrolled near the bottom."""
        if self._is_loading or self._all_loaded:
            return
        scrollbar = self.table.verticalScrollBar()
        if value >= scrollbar.maximum() * 0.8:
            self._load_data(clear=False)

    def _load_data(self, clear: bool = False) -> None:
        """Load data from database into the table incrementally."""
        if self._is_loading:
            return

        self._is_loading = True

        if clear:
            self.table.setRowCount(0)
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

        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(records))

        for i, rec in enumerate(records):
            row = start_row + i

            # Preview placeholder (Column 0)
            preview_item = QTableWidgetItem()
            preview_item.setData(Qt.ItemDataRole.UserRole, rec.id)
            preview_item.setData(Qt.ItemDataRole.UserRole + 1, rec.filepath)
            preview_item.setData(Qt.ItemDataRole.UserRole + 2, rec.url)
            self.table.setItem(row, 0, preview_item)

            # Dispatch async thumbnail
            worker = ThumbnailWorker(row, rec.filepath)
            worker.signals.finished.connect(self._on_thumbnail_ready)
            self._thread_pool.start(worker)

            # Filename (Column 1)
            self.table.setItem(row, 1, QTableWidgetItem(Path(rec.filepath).name))

            # Time (Column 2)
            self.table.setItem(
                row, 2, QTableWidgetItem(rec.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
            )

            # Size (Column 3)
            size_item = QTableWidgetItem(self._format_size(rec.size_bytes))
            size_item.setTextAlignment(
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            )
            self.table.setItem(row, 3, size_item)

            # URL (Column 4)
            self.table.setItem(row, 4, QTableWidgetItem(rec.url or ""))

        self.table.setIconSize(QSize(100, 70))

        self._current_offset += len(records)
        self._is_loading = False

        if len(records) < self._items_per_page:
            self._all_loaded = True

    @Slot(int, QImage)
    def _on_thumbnail_ready(self, row: int, img: QImage) -> None:
        """Slot called on the main thread when a thumbnail finishes decoding."""
        item = self.table.item(row, 0)
        if item:
            if img.isNull():
                icon = QIcon.fromTheme("image-missing")
            else:
                icon = QIcon(QPixmap.fromImage(img))
            item.setIcon(icon)

    # -- Selection helpers ---------------------------------------------------

    def _get_selected_record(self) -> tuple[int, str, str | None] | None:
        """Extract hidden metadata from the currently selected row."""
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        preview_item = self.table.item(row, 0)
        return (
            preview_item.data(Qt.ItemDataRole.UserRole),
            preview_item.data(Qt.ItemDataRole.UserRole + 1),
            preview_item.data(Qt.ItemDataRole.UserRole + 2),
        )

    # -- Context menu --------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        """Show contextual actions for a history record."""
        record = self._get_selected_record()
        if not record:
            return

        rec_id, filepath, url = record
        menu = QMenu(self)

        open_action = QAction("📂 Open Image", menu)
        open_action.triggered.connect(lambda: self._open_file(filepath))
        menu.addAction(open_action)

        edit_action = QAction("🖌️ Edit Image", menu)
        edit_action.triggered.connect(lambda: self._app.open_image_editor(filepath))
        menu.addAction(edit_action)

        menu.addSeparator()

        copy_img_action = QAction("🖼️ Copy Image to Clipboard", menu)
        copy_img_action.triggered.connect(lambda: self._copy_image(filepath))
        menu.addAction(copy_img_action)

        copy_path_action = QAction("📄 Copy File Path", menu)
        copy_path_action.triggered.connect(lambda: copy_text_to_clipboard(filepath))
        menu.addAction(copy_path_action)

        folder_action = QAction("📁 Open Containing Folder", menu)
        folder_action.triggered.connect(lambda: self._open_folder(filepath))
        menu.addAction(folder_action)

        if url:
            menu.addSeparator()
            copy_url_action = QAction("📋 Copy URL", menu)
            copy_url_action.triggered.connect(lambda: copy_text_to_clipboard(url))
            menu.addAction(copy_url_action)

            open_url_action = QAction("🌐 Open URL in Browser", menu)
            open_url_action.triggered.connect(lambda: self._open_url(url))
            menu.addAction(open_url_action)

        menu.addSeparator()

        upload_action = QAction("☁️ Upload Image", menu)
        upload_action.triggered.connect(lambda: self._upload_image(filepath))
        menu.addAction(upload_action)

        menu.addSeparator()

        delete_action = QAction("❌ Delete Record", menu)
        delete_action.triggered.connect(lambda: self._delete_record(rec_id))
        menu.addAction(delete_action)

        delete_file_action = QAction("🗑️ Delete File and Record", menu)
        delete_file_action.triggered.connect(lambda: self._delete_file(rec_id, filepath))
        menu.addAction(delete_file_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_double_click(self, index) -> None:
        record = self._get_selected_record()
        if record:
            self._open_file(record[1])

    # -- Actions -------------------------------------------------------------

    def _open_file(self, filepath: str) -> None:
        if Path(filepath).exists():
            subprocess.Popen(["xdg-open", filepath])
        else:
            QMessageBox.warning(
                self, "File Not Found", f"The file no longer exists:\n{filepath}"
            )

    def _open_folder(self, filepath: str) -> None:
        folder = Path(filepath).parent
        if folder.exists():
            subprocess.Popen(["xdg-open", str(folder)])

    def _open_url(self, url: str) -> None:
        import webbrowser
        webbrowser.open(url)

    def _copy_image(self, filepath: str) -> None:
        from shotx.output.clipboard import copy_image_to_clipboard
        img = QImage(filepath)
        if not img.isNull():
            copy_image_to_clipboard(img)
        else:
            QMessageBox.warning(
                self, "Warning", f"Could not load image to copy:\n{filepath}"
            )

    def _delete_record(self, rec_id: int) -> None:
        self._history_manager.delete_record(rec_id)
        self._load_data(clear=True)

    def _delete_file(self, rec_id: int, filepath: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete File",
            f"Are you sure you want to permanently delete this file from disk?\n\n{filepath}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            f = Path(filepath)
            if f.exists():
                f.unlink()
            self._history_manager.delete_record(rec_id)
            self._load_data(clear=True)

    def _upload_image(self, filepath: str) -> None:
        if Path(filepath).exists():
            self._app._start_background_upload(Path(filepath))
        else:
            QMessageBox.warning(
                self, "File Not Found", f"Cannot upload missing file:\n{filepath}"
            )

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


# ---------------------------------------------------------------------------
# HistoryDialog — thin wrapper for standalone / CLI usage (shotx --history)
# ---------------------------------------------------------------------------

class HistoryDialog(QDialog):
    """Standalone dialog that wraps HistoryWidget for CLI and tray-menu use."""

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ShotX - History")
        self.resize(900, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._history_widget = HistoryWidget(app_controller, self)
        layout.addWidget(self._history_widget)
