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

from PySide6.QtCore import QEventLoop, QRect, QThreadPool
from PySide6.QtGui import QImage

from shotx.capture import create_capture_backend, CaptureBackend
from shotx.capture.recorder import ScreenRecorder
from shotx.capture.region_detect import build_detect_regions
from shotx.config import SettingsManager, AppSettings
from shotx.output.clipboard import copy_image_to_clipboard, copy_text_to_clipboard
from shotx.output.file_saver import save_image
from shotx.ui.notification import notify_capture_success, notify_error, notify_info
from shotx.ui.overlay import RegionOverlay
from shotx.upload.worker import UploadWorker
from shotx.upload.image_hosts import ImgurUploader, ImgBBUploader
from shotx.upload.s3 import S3Uploader
from shotx.upload.ftp import FtpUploader, SftpUploader
from shotx.upload.custom import CustomUploader, SxcuParser
from shotx.upload.shortener import ShortenerWorker
from shotx.upload.base import UploaderBackend, UploadError

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

        # Screen recorder (FFmpeg / wf-recorder wrapper)
        self._recorder = ScreenRecorder(
            fps=self.settings.capture.video_fps,
            audio=self.settings.capture.capture_audio,
        )
        self._current_recording_format = "mp4"

        # Thread pool for background tasks (e.g. uploading)
        self._thread_pool = QThreadPool.globalInstance()

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

        return self._save_and_notify(image, capture_type="fullscreen")

    def capture_region(self) -> bool:
        """Capture a user-selected region of the screen.

        Workflow:
        1. Grab a fullscreen screenshot (backdrop for the overlay)
        2. Collect detectable regions (windows + AT-SPI2 widgets)
        3. Show the selection overlay
        4. Wait for user to select a region or cancel
        5. Crop the backdrop to the selected region
        6. Save + clipboard + notify

        Returns:
            True if capture succeeded.
        """
        logger.info("Starting region capture")

        # Step 1: Grab fullscreen backdrop
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            logger.error("Backdrop capture returned no image")
            self._notify_error("Could not capture screen for region selection")
            return False

        if self._verbose:
            print(f"Backdrop captured: {backdrop.width()}x{backdrop.height()}")

        # Note: GNOME's portal also copies the fullscreen screenshot to
        # clipboard. We can't prevent this (no portal option exists).
        # Our cropped region will overwrite it as the most recent entry.

        # Step 2: Collect detectable regions
        regions = []
        windows = []
        if self.settings.capture.auto_detect_regions:
            try:
                windows = self.backend.get_windows()
            except Exception as e:
                logger.warning("Window enumeration failed: %s", e)

            regions = build_detect_regions(windows, include_atspi=True)
            if self._verbose:
                print(f"Detected {len(regions)} regions ({len(windows)} windows)")

        # Step 3: Show overlay and wait for selection
        overlay = RegionOverlay(
            backdrop, 
            regions, 
            after_capture_action=self.settings.capture.after_capture_action,
            last_annotation_color=self.settings.capture.last_annotation_color,
        )

        # Persist color changes back to settings
        def _save_color(hex_color: str) -> None:
            self.settings.capture.last_annotation_color = hex_color
            self._settings_manager.save()

        # Use QEventLoop to block until the overlay signals completion
        loop = QEventLoop()
        selected_rect: list[QRect] = []  # mutable container for closure
        annotated_image: list[QImage] = []  # pre-cropped+annotated image

        def on_selected(rect: QRect) -> None:
            selected_rect.append(rect)
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        def on_annotated(img: QImage) -> None:
            annotated_image.append(img)
            loop.quit()

        overlay.region_selected.connect(on_selected)
        overlay.selection_cancelled.connect(on_cancelled)
        overlay.annotation_color_changed.connect(_save_color)
        overlay.annotated_image_ready.connect(on_annotated)
        overlay.show_fullscreen()

        loop.exec()  # Blocks until selection or cancel

        # Step 4: Process result
        if annotated_image:
            # Annotations were burned — use the pre-cropped annotated image
            cropped = annotated_image[0]
        elif selected_rect:
            rect = selected_rect[0]
            if self._verbose:
                print(f"Selected region: {rect.x()},{rect.y()} {rect.width()}x{rect.height()}")
            cropped = backdrop.copy(rect)
        else:
            if self._verbose:
                print("Region selection cancelled")
            return False

        if cropped.isNull():
            logger.error("Failed to crop backdrop to selected region")
            self._notify_error("Failed to crop selected region")
            return False

        # Step 6: Save + clipboard + notify (same pipeline as fullscreen)
        return self._save_and_notify(cropped, capture_type="region")

    # --- Recording Commands ---

    def start_recording(self, recording_format: str = "mp4") -> bool:
        """Start a screen recording session (interactive region selection)."""
        try:
            self._recorder.check_dependencies()
        except Exception as e:
            self._notify_error(str(e))
            return False

        if self._recorder.is_recording:
            return False
            
        self._current_recording_format = recording_format

        # Step 1: Capture backdrop for Region overlay
        backdrop = self.backend.capture_fullscreen()
        if not backdrop:
            self._notify_error("Failed to capture screen for region selection")
            return False

        # Step 2: Get detect regions
        regions = None
        if self.settings.capture.auto_detect_regions:
            try:
                windows = self.backend.get_windows()
                regions = build_detect_regions(windows, include_atspi=True)
            except Exception as e:
                logger.warning("Window enumeration failed: %s", e)
                regions = []

        # Step 3: Show overlay (force 'save' action to skip annotations)
        overlay = RegionOverlay(backdrop, regions, after_capture_action="save")
        loop = QEventLoop()
        selected_rect: list[QRect] = []

        def on_selected(rect: QRect) -> None:
            selected_rect.append(rect)
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        overlay.region_selected.connect(on_selected)
        overlay.selection_cancelled.connect(on_cancelled)
        overlay.show_fullscreen()
        loop.exec()

        if not selected_rect:
            if self._verbose:
                print("Recording region selection cancelled")
            return False

        rect = selected_rect[0]

        # Step 4: Determine output path
        from shotx.output.file_saver import expand_filename_pattern
        output_dir = Path(self.settings.capture.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{expand_filename_pattern(self.settings.capture.filename_pattern, capture_type='recording')}.mp4"
        output_path = output_dir / filename

        # Step 5: Start recording process
        self._recorder.start_recording(output_path, rect)
        
        # Notify tray to update UI state
        if self._tray:
            self._tray.set_recording_state(True)
            
        if self._verbose:
            print(f"Started recording to {output_path}")
            
        return True

    def stop_recording(self) -> bool:
        """Stop the active recording and process files (e.g. GIF)."""
        if not self._recorder.is_recording:
            return False
            
        video_path = self._recorder.stop_recording()
        
        if self._tray:
            self._tray.set_recording_state(False)
            
        if not video_path or not video_path.exists():
            self._notify_error("Failed to save recording")
            return False
            
        final_path = video_path

        # If GIF requested, do post-processing conversion
        if self._current_recording_format == "gif":
            from shotx.output.file_saver import expand_filename_pattern
            gif_filename = f"{expand_filename_pattern(self.settings.capture.filename_pattern, capture_type='recording')}.gif"
            gif_path = video_path.parent / gif_filename
            
            result_path = self._recorder.create_gif_from_video(video_path, gif_path)
            if result_path and result_path.exists():
                # Delete temp MP4
                try:
                    video_path.unlink()
                except OSError:
                    pass
                final_path = result_path
            else:
                self._notify_error("Failed to convert recording to GIF")

        self.last_saved_path = final_path
        
        if self._verbose:
            print(f"Saved recording to {final_path}")
            
        if self.settings.capture.show_notification:
            tray_icon = self._tray.tray_icon if self._tray else None
            notify_capture_success(tray_icon, str(final_path))
            
        return True

    def _save_and_notify(self, image: QImage, capture_type: str = "capture") -> bool:
        """Common pipeline: save → local clipboard → upload background worker → notify."""
        saved_path = None

        if self.settings.capture.save_to_file:
            saved_path = save_image(
                image=image,
                output_dir=self.settings.capture.output_dir,
                filename_pattern=self.settings.capture.filename_pattern,
                image_format=self.settings.capture.image_format,
                jpeg_quality=self.settings.capture.jpeg_quality,
                capture_type=capture_type,
            )
            if saved_path:
                self.last_saved_path = saved_path
                if self._verbose:
                    print(f"Saved to {saved_path}")
            else:
                logger.warning("Failed to save screenshot to file")

        # By default, copy the image data itself to clipboard.
        # If upload succeeds and URL copying is enabled, it will overwrite this later.
        if self.settings.capture.copy_to_clipboard:
            success = copy_image_to_clipboard(image)
            if self._verbose and success:
                print("Copied image to clipboard")

        # Kick off upload in the background if enabled and we actually saved a file
        if self.settings.upload.enabled and saved_path:
            self._start_background_upload(saved_path)
        else:
            # If not uploading, show standard success notification now
            if self.settings.capture.show_notification:
                tray_icon = self._tray.tray_icon if self._tray else None
                notify_capture_success(tray_icon, saved_path)

        return True

    def _get_uploader_for_current_settings(self) -> UploaderBackend:
        """Instantiate the correct uploader based on config."""
        uploader_target = self.settings.upload.default_uploader.lower()
        if uploader_target == "imgbb":
            return ImgBBUploader(api_key=self.settings.upload.imgbb.api_key)
        elif uploader_target == "s3":
            s3_config = self.settings.upload.s3
            return S3Uploader(
                endpoint_url=s3_config.endpoint_url if s3_config.endpoint_url else None,
                access_key=s3_config.access_key,
                secret_key=s3_config.secret_key,
                bucket_name=s3_config.bucket_name,
                public_url_format=s3_config.public_url_format if s3_config.public_url_format else None,
            )
        elif uploader_target == "ftp":
            return FtpUploader(config=self.settings.upload.ftp)
        elif uploader_target == "sftp":
            return SftpUploader(config=self.settings.upload.sftp)
        elif uploader_target.startswith("custom:"):
            # Format: 'custom:myserver' looks for `myserver.sxcu`
            sxcu_name = uploader_target.split(":", 1)[1]
            from shotx.config.settings import _default_config_dir
            sxcu_dir = Path(_default_config_dir()) / "uploaders"
            sxcu_path = sxcu_dir / f"{sxcu_name}.sxcu"
            
            try:
                sxcu_data = SxcuParser.load(sxcu_path)
            except FileNotFoundError:
                raise UploadError(
                    f"Custom uploader '{sxcu_name}' not found. "
                    f"Make sure '{sxcu_name}.sxcu' exists in {sxcu_dir}"
                )
            return CustomUploader(sxcu_data)
        else:
            # Default to Imgur
            return ImgurUploader(
                client_id=self.settings.upload.imgur.client_id,
                access_token=self.settings.upload.imgur.access_token,
            )

    def _start_background_upload(self, file_path: Path) -> None:
        """Dispatches the upload to the global QThreadPool."""
        try:
            uploader = self._get_uploader_for_current_settings()
        except UploadError as e:
            self._notify_error(str(e))
            return
            
        worker = UploadWorker(uploader, file_path)
        worker.signals.started.connect(self._on_upload_started)
        worker.signals.success.connect(self._on_upload_success)
        worker.signals.error.connect(self._on_upload_error)
        
        self._thread_pool.start(worker)

    def _on_upload_started(self, file_path: str) -> None:
        # Optional: Show an "Uploading..." notification here, 
        # but ShareX usually is silent until it succeeds to avoid spam.
        if self._verbose:
            print(f"Began background upload for: {file_path}")

    def _on_upload_success(self, file_path: str, url: str) -> None:
        """Called by the background thread when upload finishes cleanly."""
        
        # Interceptor: If URL shortener is enabled, pipe it through another worker
        if self.settings.upload.shortener.enabled:
            provider = self.settings.upload.shortener.provider
            if self._verbose:
                print(f"Shortening URL via {provider}...")
                
            shortener = ShortenerWorker(url, provider)
            shortener.signals.success.connect(lambda short_url: self._finalize_upload_success(short_url))
            self._thread_pool.start(shortener)
        else:
            self._finalize_upload_success(url)
            
    def _finalize_upload_success(self, final_url: str) -> None:
        """Final step of upload: clipboard and notification."""
        if self.settings.upload.copy_url_to_clipboard:
            copy_text_to_clipboard(final_url)
            if self._verbose:
                print(f"Copied URL to clipboard: {final_url}")
            
        if self.settings.capture.show_notification:
            tray_icon = self._tray.tray_icon if self._tray else None
            # Standard notify success, but the clipboard will have the URL now
            notify_info(tray_icon, "Upload Successful", f"Link copied to clipboard:\n{final_url}")
            
    def _on_upload_error(self, file_path: str, error_msg: str) -> None:
        """Called by the background thread on upload failure."""
        self._notify_error(error_msg)
        
        # We still want to notify them the local capture was saved, even if upload failed
        if self.settings.capture.show_notification:
            tray_icon = self._tray.tray_icon if self._tray else None
            notify_capture_success(tray_icon, Path(file_path))

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
            success = self.capture_region()
            return 0 if success else 1
        elif capture_type == "window":
            # Window capture uses the same overlay — user clicks a window
            success = self.capture_region()
            return 0 if success else 1
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
