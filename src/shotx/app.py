"""ShotX application controller.

This is the central orchestrator that connects capture backends,
output handlers, and UI components. All capture workflows flow
through this class.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from shotx.capture import create_capture_backend, CaptureBackend
from shotx.config import SettingsManager, AppSettings
from shotx.output.clipboard import copy_image_to_clipboard
from shotx.output.file_saver import save_image
from shotx.ui.notification import notify_capture_success, notify_error

logger = logging.getLogger(__name__)


class ShotXApp:
    """Main application controller.

    Owns and coordinates all components:
    - Settings manager (config load/save)
    - Capture backend (Wayland or X11)
    - System tray icon + context menu
    - Hotkey manager

    Public methods like capture_fullscreen() are called from the tray
    menu, hotkey callbacks, and CLI one-shot mode.
    """

    def __init__(self, config_dir: str | None = None, verbose: bool = False) -> None:
        self._verbose = verbose
        self._setup_logging()

        # Settings
        self._settings_manager = SettingsManager(config_dir=config_dir)

        # Capture backend (auto-detected)
        self._backend: CaptureBackend | None = None

        # UI components (created lazily when running as tray app)
        self._tray: "TrayIcon | None" = None

        # Track last saved file (for notification click → open)
        self.last_saved_path: Path | None = None

    @property
    def settings(self) -> AppSettings:
        """Access current settings."""
        return self._settings_manager.settings

    @property
    def backend(self) -> CaptureBackend:
        """Access capture backend, creating it on first use."""
        if self._backend is None:
            self._backend = create_capture_backend()
            if self._verbose:
                print(f"Using {self._backend.name} capture backend")
        return self._backend

    def capture_fullscreen(self, monitor_index: int | None = None) -> bool:
        """Capture the full screen, save, and copy to clipboard.

        This is the core capture workflow:
        1. Grab pixels from the screen
        2. Save to file (if enabled)
        3. Copy to clipboard (if enabled)
        4. Show notification (if enabled)

        Args:
            monitor_index: Specific monitor to capture (None = primary).

        Returns:
            True if capture succeeded.
        """
        logger.info("Capturing fullscreen (monitor=%s)", monitor_index)

        try:
            image = self.backend.capture_fullscreen(monitor_index)
        except Exception as e:
            logger.error("Capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False

        if image is None or image.isNull():
            logger.error("Capture returned no image")
            self._notify_error("Screenshot capture failed — no image returned")
            return False

        if self._verbose:
            print(f"Captured {image.width()}x{image.height()} image")

        saved_path = None

        # Save to file
        if self.settings.capture.save_to_file:
            saved_path = save_image(
                image=image,
                output_dir=self.settings.capture.output_dir,
                filename_pattern=self.settings.capture.filename_pattern,
                image_format=self.settings.capture.image_format,
                jpeg_quality=self.settings.capture.jpeg_quality,
                capture_type="fullscreen",
            )
            if saved_path:
                self.last_saved_path = saved_path
                if self._verbose:
                    print(f"Saved to {saved_path}")
            else:
                logger.warning("Failed to save screenshot to file")

        # Copy to clipboard
        if self.settings.capture.copy_to_clipboard:
            success = copy_image_to_clipboard(image)
            if self._verbose and success:
                print("Copied to clipboard")

        # Show notification
        if self.settings.capture.show_notification:
            tray_icon = self._tray.tray_icon if self._tray else None
            notify_capture_success(tray_icon, saved_path)

        return True

    def run_tray(self) -> int:
        """Run ShotX as a system tray application.

        Creates the tray icon with context menu and enters the Qt
        event loop. The app stays running until Quit is selected.

        Returns:
            Exit code (0 = success).
        """
        # Prevent running without a display
        app = QApplication.instance()
        if app is None:
            logger.error("No QApplication — cannot run tray app")
            return 1

        # Ensure the app doesn't quit when the last window closes
        # (we want it to keep running in the tray)
        app.setQuitOnLastWindowClosed(False)

        # Create tray icon
        from shotx.ui.tray import TrayIcon
        self._tray = TrayIcon(self)
        self._tray.show()

        logger.info("ShotX tray app started")
        if self._verbose:
            print(f"ShotX running in system tray ({self.backend.name} backend)")
            print("Right-click the tray icon for options, or press Print Screen to capture")

        return app.exec()

    def run_oneshot(self, capture_type: str, **kwargs: object) -> int:
        """Run a one-shot capture from CLI and exit.

        Args:
            capture_type: One of 'fullscreen', 'region', 'window'.

        Returns:
            Exit code (0 = success, 1 = failure).
        """
        if capture_type == "fullscreen":
            success = self.capture_fullscreen()
            return 0 if success else 1
        elif capture_type == "region":
            print("Region capture will be available in Phase 2.")
            return 1
        elif capture_type == "window":
            print("Window capture will be available in Phase 2.")
            return 1
        else:
            print(f"Unknown capture type: {capture_type}")
            return 1

    # --- Private methods ---

    def _setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        level = logging.DEBUG if self._verbose else logging.WARNING
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    def _notify_error(self, message: str) -> None:
        """Show error via notification or stderr."""
        tray_icon = self._tray.tray_icon if self._tray else None
        notify_error(tray_icon, message)
        if self._verbose:
            print(f"Error: {message}", file=sys.stderr)
