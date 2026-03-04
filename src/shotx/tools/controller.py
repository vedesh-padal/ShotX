"""Tool controller.

Owns the launching of standalone tool dialogs: Image Editor,
Hash Checker, Directory Indexer, and History Viewer.

Extracted from the former god-class ``ShotXApp`` in ``app.py``.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Slot

from shotx.config.settings import SettingsManager
from shotx.core.events import event_bus

logger = logging.getLogger(__name__)


class ToolController(QObject):
    """Manages standalone tool dialog lifecycles.

    Listens to ``event_bus.tool_requested`` and dispatches to the
    appropriate dialog launcher.
    """

    def __init__(
        self,
        settings_manager: SettingsManager,
        history_manager: object,
        *,
        verbose: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings_manager
        self._history = history_manager
        self._verbose = verbose

        # Keep references to prevent GC
        self._hash_dialog = None
        self._indexer_dialog = None
        self._image_editor = None

        # Wire EventBus
        event_bus.tool_requested.connect(self._on_tool_requested)
        event_bus.tool_requested_with_args.connect(self._on_tool_requested_with_args)

    @property
    def settings(self):
        return self._settings.settings

    # ------------------------------------------------------------------
    # EventBus dispatchers
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_tool_requested(self, tool_name: str) -> None:
        dispatch = {
            "hash": self.open_hash_checker,
            "indexer": self.open_directory_indexer,
            "editor": self.open_image_editor,
            "history": self.open_history_viewer,
        }
        handler = dispatch.get(tool_name)
        if handler:
            handler()
        else:
            logger.warning("Unknown tool requested: %s", tool_name)

    @Slot(str, dict)
    def _on_tool_requested_with_args(self, tool_name: str, kwargs: dict) -> None:
        if tool_name == "editor":
            self.open_image_editor(**kwargs)
        elif tool_name == "indexer":
            self.open_directory_indexer(**kwargs)
        elif tool_name == "hash":
            self.open_hash_checker(**kwargs)
        elif tool_name == "history":
            self.open_history_viewer(**kwargs)
        else:
            logger.warning("Unknown tool requested (with args): %s", tool_name)

    # ------------------------------------------------------------------
    # Tool launchers
    # ------------------------------------------------------------------

    def open_hash_checker(self, exec_dialog: bool = False) -> bool:
        """Open the hash checker tool dialog."""
        from shotx.ui.hash_dialog import HashDialog

        self._hash_dialog = HashDialog()
        if exec_dialog:
            self._hash_dialog.exec()
        else:
            self._hash_dialog.show()
        return True

    def open_directory_indexer(
        self, start_path: str = "", exec_dialog: bool = False
    ) -> bool:
        """Open the directory indexer tool dialog."""
        from shotx.ui.directory_indexer import DirectoryIndexerDialog

        self._indexer_dialog = DirectoryIndexerDialog(initial_dir=start_path)
        if exec_dialog:
            self._indexer_dialog.exec()
        else:
            self._indexer_dialog.show()
        return True

    def open_image_editor(
        self, initial_image_path: str = "", exec_loop: bool = False
    ) -> bool:
        """Open the full image editor."""
        from shotx.ui.editor import ImageEditorWindow
        from PySide6.QtGui import QImage

        initial_image = None
        if initial_image_path:
            initial_image = QImage(initial_image_path)

        self._image_editor = ImageEditorWindow(initial_image=initial_image)
        self._image_editor.show()

        if exec_loop:
            from PySide6.QtCore import QEventLoop

            loop = QEventLoop()
            original_closeEvent = self._image_editor.closeEvent

            def new_closeEvent(event):
                loop.quit()
                original_closeEvent(event)

            self._image_editor.closeEvent = new_closeEvent
            loop.exec()

        return True

    def open_history_viewer(self, exec_dialog: bool = False) -> bool:
        """Open the History viewer.

        In tray mode, emits a signal to open the Main Window.
        In CLI oneshot mode, opens the standalone HistoryDialog.
        """
        if exec_dialog:
            from shotx.ui.history import HistoryDialog

            dialog = HistoryDialog(self._history)
            dialog.exec()
            return True

        # In tray mode, request the main window to open and switch to history
        event_bus.open_main_window_requested.emit()
        return True
