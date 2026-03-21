"""History Viewer UI for ShotX.

Displays a tabulated view of past captures loaded from the SQLite database,
with a side-by-side image preview panel (QSplitter) and a rich right-click
context menu mirroring the ShareX "History" window.

HistoryWidget is the embeddable QWidget used inside the Main Window.
HistoryDialog is a thin QDialog wrapper for standalone / CLI / tray usage.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QIcon, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shotx.output.clipboard import copy_text_to_clipboard
from shotx.ui.theme import Theme

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
    """Embeddable history viewer widget with async thumbnails, infinite scroll,
    a split-pane preview panel, and a ShareX-style context menu."""

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app = app_controller
        self._history_manager = self._app._history_manager

        self._thread_pool = QThreadPool.globalInstance()
        self._items_per_page = 50
        self._current_offset = 0
        self._is_loading = False
        self._all_loaded = False
        self._search_query = ""

        self._setup_ui()
        self._load_data(clear=True)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tools bar
        tools_layout = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 File name, date/time, URL...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        tools_layout.addWidget(self._search_input, stretch=1)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(lambda: self._load_data(clear=True))
        tools_layout.addWidget(self.btn_refresh)

        self.btn_clear = QPushButton("🗑️ Clear History")
        self.btn_clear.clicked.connect(self._on_clear_history)
        tools_layout.addWidget(self.btn_clear)

        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        # ----- Split pane: Table | Preview -----
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Preview", "Filename", "Time", "Size", "URL"
        ])

        # Table configurations
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Theme.BASE_DARK};
                alternate-background-color: {Theme.BASE_LIGHTER};
                color: {Theme.TEXT_PRIMARY};
                gridline-color: transparent;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {Theme.ACCENT_PURPLE};
                color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: {Theme.BASE_LIGHTER};
                color: {Theme.TEXT_SECONDARY};
                padding: 4px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }}
        """)

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

        # Selection changed → update preview
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        # Infinite scroll
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._splitter.addWidget(self.table)

        # Right: Preview panel
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_label.setMinimumWidth(250)
        self._preview_label.setStyleSheet(
            f"QLabel {{ background-color: {Theme.BASE_DARK}; border: none; }}"
        )
        self._preview_label.setText("Select an item to preview")

        self._splitter.addWidget(self._preview_label)
        self._splitter.setStretchFactor(0, 3)  # Table gets 3/4 of space
        self._splitter.setStretchFactor(1, 1)  # Preview gets 1/4

        layout.addWidget(self._splitter)

        # Listen for new/updated captures via EventBus
        from shotx.core.events import event_bus
        event_bus.capture_completed.connect(lambda f, s, t: self._load_data(clear=True))

    # -- Formatting helpers --------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable string."""
        if size_bytes == 0:
            return "0 B"
        sizes = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        f_size = float(size_bytes)
        while f_size >= 1024 and i < len(sizes) - 1:
            f_size /= 1024.0
            i += 1
        return f"{f_size:.1f} {sizes[i]}"

    # -- Preview panel -------------------------------------------------------

    def _on_selection_changed(self) -> None:
        """Update the preview panel when a row is selected."""
        record = self._get_selected_record()
        if not record:
            self._preview_label.setText("Select an item to preview")
            return

        _rec_id, filepath, _url = record
        if not Path(filepath).exists():
            self._preview_label.setText("⚠️ File not found on disk")
            return

        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            self._preview_label.setText("⚠️ Could not load image")
            return

        # Scale the pixmap to fit the preview label while preserving aspect ratio
        scaled = pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    # -- Search --------------------------------------------------------------

    def _on_search(self) -> None:
        """Run the search when Enter is pressed."""
        self._search_query = self._search_input.text().strip()
        self._load_data(clear=True)

    def _on_search_text_changed(self, text: str) -> None:
        """Live-search: reload when the search box is cleared."""
        if not text and self._search_query:
            self._search_query = ""
            self._load_data(clear=True)

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
            limit=self._items_per_page, offset=self._current_offset,
            search=self._search_query,
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
        if preview_item is None:
            return None
        return (
            preview_item.data(Qt.ItemDataRole.UserRole),
            preview_item.data(Qt.ItemDataRole.UserRole + 1),
            preview_item.data(Qt.ItemDataRole.UserRole + 2),
        )

    def _get_all_selected_records(self) -> list[tuple[int, str, str | None]]:
        """Extract metadata from ALL selected rows (for batch operations)."""
        seen_rows: set[int] = set()
        records = []
        for item in self.table.selectedItems():
            r = item.row()
            if r in seen_rows:
                continue
            seen_rows.add(r)
            preview_item = self.table.item(r, 0)
            if preview_item:
                records.append((
                    preview_item.data(Qt.ItemDataRole.UserRole),
                    preview_item.data(Qt.ItemDataRole.UserRole + 1),
                    preview_item.data(Qt.ItemDataRole.UserRole + 2),
                ))
        return records

    # -- Context menu --------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        """Show ShareX-style contextual actions for a history record."""
        record = self._get_selected_record()
        if not record:
            return

        rec_id, filepath, url = record
        file_exists = Path(filepath).exists()
        has_url = bool(url)
        filename = Path(filepath).name

        menu = QMenu(self)

        # ---- Open submenu ----
        open_menu = menu.addMenu("📂 Open")

        a_open_file = open_menu.addAction("File")
        a_open_file.setEnabled(file_exists)
        a_open_file.triggered.connect(lambda: self._open_file(filepath))

        a_open_folder = open_menu.addAction("Folder")
        a_open_folder.setEnabled(file_exists)
        a_open_folder.triggered.connect(lambda: self._open_folder(filepath))

        if has_url:
            a_open_url = open_menu.addAction("URL in Browser")
            a_open_url.triggered.connect(lambda: self._open_url(url) if url else None)

        # ---- Copy submenu ----
        copy_menu = menu.addMenu("📋 Copy")

        a_copy_image = copy_menu.addAction("Image")
        a_copy_image.setShortcut("Alt+C")
        a_copy_image.setEnabled(file_exists)
        a_copy_image.triggered.connect(lambda: self._copy_image(filepath))

        a_copy_file = copy_menu.addAction("File")
        a_copy_file.setShortcut("Shift+C")
        a_copy_file.setEnabled(file_exists)
        a_copy_file.triggered.connect(
            lambda: copy_text_to_clipboard(filepath) if filepath else None
        )

        copy_menu.addSeparator()

        a_copy_url = copy_menu.addAction("URL")
        a_copy_url.setShortcut("Ctrl+C")
        a_copy_url.setEnabled(has_url)
        a_copy_url.triggered.connect(lambda: copy_text_to_clipboard(url) if url else None)

        copy_menu.addSeparator()

        a_copy_path = copy_menu.addAction("File path")
        a_copy_path.setShortcut("Ctrl+Shift+C")
        a_copy_path.triggered.connect(lambda: copy_text_to_clipboard(filepath))

        a_copy_filename = copy_menu.addAction("File name")
        a_copy_filename.triggered.connect(
            lambda: copy_text_to_clipboard(filename)
        )

        a_copy_filename_ext = copy_menu.addAction("File name with extension")
        a_copy_filename_ext.triggered.connect(
            lambda: copy_text_to_clipboard(filename)
        )

        a_copy_folder = copy_menu.addAction("Folder")
        a_copy_folder.triggered.connect(
            lambda: copy_text_to_clipboard(str(Path(filepath).parent))
        )

        copy_menu.addSeparator()

        # Markdown / HTML link formats (only when URL is present)
        a_md_link = copy_menu.addAction("Markdown link")
        a_md_link.setEnabled(has_url)
        a_md_link.triggered.connect(
            lambda: copy_text_to_clipboard(f"[{filename}]({url})")
        )

        a_md_img = copy_menu.addAction("Markdown image")
        a_md_img.setEnabled(has_url)
        a_md_img.triggered.connect(
            lambda: copy_text_to_clipboard(f"![{filename}]({url})")
        )

        a_md_linked_img = copy_menu.addAction("Markdown linked image")
        a_md_linked_img.setEnabled(has_url)
        a_md_linked_img.triggered.connect(
            lambda: copy_text_to_clipboard(f"[![{filename}]({url})]({url})")
        )

        a_html_link = copy_menu.addAction("HTML link")
        a_html_link.setEnabled(has_url)
        a_html_link.triggered.connect(
            lambda: copy_text_to_clipboard(
                f'<a href="{url}">{filename}</a>'
            )
        )

        a_html_img = copy_menu.addAction("HTML linked image")
        a_html_img.setEnabled(has_url)
        a_html_img.triggered.connect(
            lambda: copy_text_to_clipboard(
                f'<a href="{url}"><img src="{url}" alt="{filename}"></a>'
            )
        )

        menu.addSeparator()

        # ---- Image preview ----
        a_preview = menu.addAction("🖼️ Image preview...")
        a_preview.setEnabled(file_exists)
        a_preview.triggered.connect(lambda: self._open_file(filepath))

        # ---- Upload / Edit ----
        a_upload = menu.addAction("☁️ Upload file")
        a_upload.setEnabled(file_exists)
        a_upload.triggered.connect(lambda: self._upload_image(filepath))

        a_edit = menu.addAction("🖌️ Edit image...")
        a_edit.setEnabled(file_exists)
        a_edit.triggered.connect(lambda: self._edit_image(filepath))

        menu.addSeparator()

        # ---- Delete (multi-select aware) ----
        all_selected = self._get_all_selected_records()
        count = len(all_selected)
        suffix = f" ({count} items)" if count > 1 else ""

        a_remove = menu.addAction(f"📤 Remove from list{suffix}")
        a_remove.triggered.connect(lambda: self._delete_records_batch(all_selected))

        a_delete_file = menu.addAction(f"🗑️ Delete file(s) locally...{suffix}")
        a_delete_file.triggered.connect(lambda: self._delete_files_batch(all_selected))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_double_click(self, index) -> None:
        record = self._get_selected_record()
        if record:
            self._open_file(record[1])

    # -- Actions -------------------------------------------------------------

    def _open_file(self, filepath: str) -> None:
        if Path(filepath).exists():
            from shotx.core.xdg import open_file
            open_file(filepath)
        else:
            QMessageBox.warning(
                self, "File Not Found", f"The file no longer exists:\n{filepath}"
            )

    def _open_folder(self, filepath: str) -> None:
        folder = Path(filepath).parent
        if folder.exists():
            from shotx.core.xdg import open_folder
            open_folder(folder)

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

    def _edit_image(self, filepath: str) -> None:
        """Launch the image editor with the selected file."""
        from shotx.core.events import event_bus
        event_bus.tool_requested_with_args.emit(
            "editor", {"initial_image_path": filepath}
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

    def _delete_records_batch(self, records: list[tuple[int, str, str | None]]) -> None:
        """Remove multiple records from the history database."""
        for rec_id, _fp, _url in records:
            self._history_manager.delete_record(rec_id)
        self._load_data(clear=True)

    def _delete_files_batch(self, records: list[tuple[int, str, str | None]]) -> None:
        """Delete multiple files from disk and remove their DB records."""
        count = len(records)
        reply = QMessageBox.question(
            self,
            "Delete Files",
            f"Are you sure you want to permanently delete {count} file(s) from disk?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for rec_id, filepath, _url in records:
                f = Path(filepath)
                if f.exists():
                    f.unlink()
                self._history_manager.delete_record(rec_id)
            self._load_data(clear=True)

    def _upload_image(self, filepath: str) -> None:
        if Path(filepath).exists():
            from shotx.core.events import event_bus
            event_bus.upload_requested.emit(filepath)
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
# HistoryDialog — standalone floating window (ShareX "History" paradigm)
# ---------------------------------------------------------------------------

class HistoryDialog(QDialog):
    """Standalone dialog that wraps HistoryWidget for CLI, tray-menu,
    and sidebar 'History...' button use."""

    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ShotX - History")
        self.resize(1100, 650)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._history_widget = HistoryWidget(app_controller, self)
        layout.addWidget(self._history_widget)
