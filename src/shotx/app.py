"""ShotX application orchestrator.

Thin dependency-injection container that wires together controllers,
event bus, and UI components.  All business logic lives in the
dedicated controllers:

- ``capture.controller.CaptureController``
- ``upload.controller.UploadController``
- ``tools.controller.ToolController``
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, QThreadPool, Slot
from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon

from shotx.config import AppSettings, SettingsManager
from shotx.config.settings import _default_config_dir
from shotx.core.events import event_bus

if TYPE_CHECKING:
    from shotx.ui.tray import TrayIcon
from shotx.core.tasks import task_manager
from shotx.db.history import HistoryManager
from shotx.ui.notification import init_notifications, notify_error, notify_info

logger = logging.getLogger(__name__)


class ShotXApp(QObject):
    """Application orchestrator.

    Instantiates the EventBus, controllers, and UI shell, then wires
    them together.  No capture/upload/tool logic lives here any more.
    """

    # --- Internal State ---
    _tray: TrayIcon | None = None
    tray_icon: QSystemTrayIcon | None = None
    last_saved_path: Path | None = None
    _main_window: QMainWindow | None = None

    def __init__(self, config_dir: str | None = None, verbose: bool = False) -> None:
        super().__init__()
        self._verbose = verbose
        self._setup_logging()

        # --- Core services ---
        self._settings_manager = SettingsManager(config_dir=config_dir)
        db_path = Path(_default_config_dir()) / "history.db"
        self._history_manager = HistoryManager(db_path)

        # --- Controllers (imported here to avoid top-level circular deps
        #     until remaining UI files are fully decoupled) ---
        from shotx.capture.controller import CaptureController
        from shotx.tools.controller import ToolController
        from shotx.upload.controller import UploadController

        self._capture = CaptureController(
            self._settings_manager,
            self._history_manager,
            verbose=verbose,
        )
        self._upload = UploadController(
            self._settings_manager,
            self._history_manager,
            verbose=verbose,
        )
        self._tools = ToolController(
            self._settings_manager,
            self._history_manager,
            verbose=verbose,
        )

        # --- Notification routing ---
        # Controllers emit EventBus signals; we route them to the
        # notification subsystem here so controllers never import UI code
        # for notifications.
        event_bus.notify_error_requested.connect(self._on_notify_error)
        event_bus.notify_info_requested.connect(self._on_notify_info)
        event_bus.open_main_window_requested.connect(self.open_main_window)

        # --- UI components (lazy) ---
        self._tray = None
        self._main_window = None

        # --- Global hotkeys ---
        from shotx.ui.hotkeys import HotkeyManager
        self._hotkeys = HotkeyManager()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def settings(self) -> AppSettings:
        """Access current settings."""
        return self._settings_manager.settings

    @property
    def backend(self):
        """Access capture backend (delegates to CaptureController)."""
        return self._capture.backend

    # ------------------------------------------------------------------
    # Tray mode
    # ------------------------------------------------------------------

    def run_tray(self) -> int:
        """Run ShotX as a system tray application."""
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        init_notifications()

        app = QApplication.instance()
        if app is None:
            logger.error("No QApplication — cannot run tray app")
            return 1

        if isinstance(app, QApplication):
            app.setQuitOnLastWindowClosed(False)



        from shotx.ui.tray import TrayIcon
        self._tray = TrayIcon(self)
        self.tray_icon = self._tray.tray_icon
        self.tray_icon.show()

        logger.info("ShotX tray app started")
        self.apply_hotkeys()

        if self._verbose:
            print(f"ShotX running in system tray ({self.backend.name} backend)")
            print("Right-click the tray icon for options, or press Print Screen to capture")

        return app.exec()

    # ------------------------------------------------------------------
    # One-shot CLI mode
    # ------------------------------------------------------------------

    def run_oneshot(self, capture_type: str, **kwargs: object) -> int:
        """Run a one-shot command from CLI and exit."""
        success = False

        # Capture domain
        if capture_type in (
            "fullscreen", "region", "window", "ocr", "color_picker",
            "ruler", "qr_scan", "qr_generate", "qr_scan_clipboard", "pin_region",
        ):
            capture_map = {"window": "region"}
            mapped = capture_map.get(capture_type, capture_type)
            handler = getattr(self._capture, f"capture_{mapped}", None)
            if handler is None:
                handler = getattr(self._capture, mapped, None)
            if handler:
                success = handler()
            else:
                print(f"Unknown capture type: {capture_type}")
                return 1

        # Upload domain
        elif capture_type == "shorten_url":
            url = cast("str | None", kwargs.get("url"))
            success = self._upload.shorten_clipboard_url(headless=True, url=url)

        # Tool domain
        elif capture_type == "hash":
            success = self._tools.open_hash_checker(exec_dialog=True)
        elif capture_type == "index_dir":
            start_path = cast(str, kwargs.get("start_path", ""))
            success = self._tools.open_directory_indexer(start_path, exec_dialog=True)
        elif capture_type == "edit":
            image_path = cast(str, kwargs.get("image_path", ""))
            success = self._tools.open_image_editor(image_path, exec_loop=True)
        elif capture_type == "history":
            success = self._tools.open_history_viewer(exec_dialog=True)

        else:
            print(f"Unknown capture type: {capture_type}")
            return 1

        # Drain thread pool so background workers (uploads) can finish
        pool = QThreadPool.globalInstance()
        if success and (pool.activeThreadCount() > 0 or task_manager.active_count > 0):
            if self._verbose:
                print("Waiting for background tasks to finish...")

            app = QApplication.instance()
            start_time = time.time()

            while pool.activeThreadCount() > 0 or task_manager.active_count > 0:
                if time.time() - start_time > 30.0:
                    if self._verbose:
                        print("Background task timed out.")
                    break
                if app:
                    app.processEvents()
                time.sleep(0.05)

            # Flush remaining queued signals
            if app:
                app.processEvents()
                time.sleep(0.1)
                app.processEvents()

        return 0 if success else 1

    # ------------------------------------------------------------------
    # UI wiring (still coupled until Step 9 decouples tray/main_window)
    # ------------------------------------------------------------------

    def open_main_window(self) -> None:
        """Open (or raise) the unified ShotX Main Window."""
        logger.info("Opening Main Window")
        from shotx.ui.main_window import ShotXMainWindow

        if self._main_window is None:
            self._main_window = ShotXMainWindow(self)

        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def open_settings_dialog(self) -> None:
        """Open the Settings dialog directly."""
        logger.info("Opening Settings dialog")
        if self._main_window and self._main_window.isVisible():
            from shotx.ui.main_window import ShotXMainWindow
            cast(ShotXMainWindow, self._main_window)._on_app_settings()
        else:
            from shotx.ui.settings_dialog import ApplicationSettingsDialog
            dialog = ApplicationSettingsDialog(self._settings_manager, parent=None)
            dialog.exec()
            # Re-apply hotkeys in case they were changed
            self.apply_hotkeys()

    def open_history_viewer(self, exec_dialog: bool = False) -> bool:
        """Open the History viewer."""
        return self._tools.open_history_viewer(exec_dialog=exec_dialog)

    def apply_hotkeys(self) -> None:
        """Register all configured keyboard shortcuts from settings."""
        self._hotkeys.unregister_all()

        bindings = [
            (self.settings.hotkeys.capture_fullscreen, self._capture.capture_fullscreen, "Fullscreen"),
            (self.settings.hotkeys.capture_region, self._capture.capture_region, "Region"),
            (self.settings.hotkeys.capture_window, self._capture.capture_region, "Window"),
            (self.settings.hotkeys.capture_ocr, self._capture.capture_ocr, "OCR"),
            (self.settings.hotkeys.capture_color_picker, self._capture.capture_color_picker, "Color Picker"),
            (self.settings.hotkeys.capture_ruler, self._capture.capture_ruler, "Ruler"),
            (self.settings.hotkeys.capture_qr_scan, self._capture.capture_qr_scan, "QR Scan"),
            (self.settings.hotkeys.pin_region, self._capture.pin_region, "Pin Region"),
        ]

        for keys, handler, desc in bindings:
            if keys.strip():
                from collections.abc import Callable
                from typing import Any, cast
                self._hotkeys.register(keys.strip(), cast(Callable[[], Any], handler), desc)

    # ------------------------------------------------------------------
    # Delegated methods (backward compat for UI modules still using self._app)
    # ------------------------------------------------------------------

    def capture_fullscreen(self, **kw) -> bool:
        return self._capture.capture_fullscreen(**kw)

    def capture_region(self) -> bool:
        return self._capture.capture_region()

    def capture_ocr(self) -> bool:
        return self._capture.capture_ocr()

    def capture_color_picker(self) -> bool:
        return self._capture.capture_color_picker()

    def capture_ruler(self) -> bool:
        return self._capture.capture_ruler()

    def capture_qr_scan(self) -> bool:
        return self._capture.capture_qr_scan()

    def generate_qr_from_clipboard(self) -> bool:
        return self._capture.generate_qr_from_clipboard()

    def scan_qr_from_clipboard(self) -> bool:
        return bool(self._capture.scan_qr_from_clipboard())

    def pin_region(self) -> bool:
        return bool(self._capture.pin_region())

    def start_recording(self, fmt: str = "mp4") -> bool:
        return bool(self._capture.start_recording(fmt))

    def stop_recording(self) -> bool:
        return bool(self._capture.stop_recording())

    def open_hash_checker(self, **kw) -> bool:
        return self._tools.open_hash_checker(**kw)

    def open_directory_indexer(self, start_path: str = "", **kw) -> bool:
        return self._tools.open_directory_indexer(start_path, **kw)

    def open_image_editor(self, path: str = "", **kw) -> bool:
        return self._tools.open_image_editor(path, **kw)

    def shorten_clipboard_url(self, **kw) -> bool:
        return self._upload.shorten_clipboard_url(**kw)

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        level = logging.DEBUG if self._verbose else logging.WARNING
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        if self._verbose:
            logging.getLogger("httpcore").setLevel(logging.INFO)
            logging.getLogger("httpx").setLevel(logging.INFO)
            logging.getLogger("asyncio").setLevel(logging.INFO)

    @Slot(str)
    def _on_notify_error(self, message: str) -> None:
        """Route EventBus error notifications to the notification subsystem."""
        tray_icon = getattr(self._tray, "tray_icon", None) if self._tray else None
        notify_error(tray_icon, message)
        if self._verbose:
            print(f"Error: {message}", file=sys.stderr)

    @Slot(str, str)
    def _on_notify_info(self, title: str, message: str) -> None:
        """Route EventBus info notifications to the notification subsystem."""
        tray_icon = getattr(self._tray, "tray_icon", None) if self._tray else None
        notify_info(tray_icon, title, message)

    # Backward compat aliases used by older UI code
    def _notify_error(self, message: str) -> None:
        self._on_notify_error(message)

    def _notify_info(self, title: str, message: str) -> None:
        self._on_notify_info(title, message)
