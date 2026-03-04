"""ShotX application controller.

This is the central orchestrator that connects capture backends,
output handlers, and UI components. All capture workflows flow
through this class.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from PySide6.QtCore import QEventLoop, QRect, QThreadPool, QObject, Slot
from PySide6.QtGui import QImage

from shotx.capture import create_capture_backend, CaptureBackend
from shotx.capture.recorder import ScreenRecorder
from shotx.capture.region_detect import build_detect_regions
from shotx.config import SettingsManager, AppSettings
from shotx.output.clipboard import copy_image_to_clipboard, copy_text_to_clipboard
from shotx.output.file_saver import save_image
from shotx.ui.notification import notify_capture_success, notify_error, notify_info, init_notifications
from shotx.ui.overlay import RegionOverlay
from shotx.upload.worker import UploadWorker
from shotx.upload.image_hosts import ImgurUploader, ImgBBUploader, TmpfilesUploader
from shotx.upload.s3 import S3Uploader
from shotx.upload.ftp import FtpUploader, SftpUploader
from shotx.upload.custom import CustomUploader, SxcuParser
from shotx.upload.shortener import ShortenerWorker
from shotx.upload.base import UploaderBackend, UploadError
from shotx.db.history import HistoryManager

logger = logging.getLogger(__name__)


class ShotXApp(QObject):
    """Main application controller.

    Owns and coordinates all components:
    - Settings manager (config load/save)
    - Capture backend (Wayland or X11)
    - System tray icon + context menu
    - Hotkey manager

    Public methods like capture_fullscreen() are called from the tray
    menu, hotkey callbacks, and CLI one-shot mode.
    """

    # Emitted when a capture is successfully saved to disk and DB (filepath, size_bytes, capture_type)
    from PySide6.QtCore import Signal
    capture_saved = Signal(str, int, str)
    
    # Emitted when an existing capture is updated (e.g., upload finished, URL added). Payload: filepath
    capture_updated = Signal(str)

    def __init__(self, config_dir: str | None = None, verbose: bool = False) -> None:
        super().__init__()
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

        # History database
        from shotx.config.settings import _default_config_dir
        db_path = Path(_default_config_dir()) / "history.db"
        self._history_manager = HistoryManager(db_path)

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

        delay_sec = self.settings.capture.screenshot_delay
        if delay_sec > 0:
            logger.info("Waiting %d seconds before fullscreen capture...", delay_sec)
            from PySide6.QtCore import QEventLoop, QTimer
            loop = QEventLoop()
            QTimer.singleShot(int(delay_sec * 1000), loop.quit)
            loop.exec()

        try:
            image = self.backend.capture_fullscreen(
                monitor_index=monitor_index,
                show_cursor=self.settings.capture.show_cursor,
            )
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

        delay_sec = self.settings.capture.screenshot_delay
        if delay_sec > 0:
            logger.info("Waiting %d seconds before region capture backdrop...", delay_sec)
            from PySide6.QtCore import QEventLoop, QTimer
            loop = QEventLoop()
            QTimer.singleShot(int(delay_sec * 1000), loop.quit)
            loop.exec()

        # Step 1: Grab fullscreen backdrop
        try:
            backdrop = self.backend.capture_fullscreen(
                show_cursor=self.settings.capture.show_cursor
            )
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

    def capture_ocr(self) -> bool:
        """Capture a region and apply Tesseract OCR to extract text."""
        logger.info("Starting OCR capture")
        
        # Step 1: Capture fullscreen backdrop
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False
            
        if backdrop is None or backdrop.isNull():
            return False
            
        # Step 2: Overlay for region selection
        windows = []
        regions = []
        if self.settings.capture.auto_detect_regions:
            try:
                from shotx.capture.detect import get_windows, build_detect_regions
                windows = get_windows(self.backend.name)
                regions = build_detect_regions(windows, include_atspi=True)
            except Exception:
                pass

        from shotx.ui.overlay import RegionOverlay
        from PySide6.QtCore import QEventLoop, QRect

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
            return False

        cropped = backdrop.copy(selected_rect[0])
        if cropped.isNull():
            return False

        # Step 3: Run OCR
        from shotx.tools.ocr import extract_text, TesseractNotFoundError
        try:
            text = extract_text(cropped)
        except TesseractNotFoundError:
            self._notify_error("Tesseract missing. Please install 'tesseract-ocr'.")
            return False
        except Exception as e:
            logger.error("OCR failed: %s", e)
            self._notify_error(f"OCR Exception: {e}")
            return False

        # Step 4: Clipboard & Notify
        if text:
            from shotx.output.clipboard import copy_text_to_clipboard
            success = copy_text_to_clipboard(text)
            if success:
                from shotx.ui.notification import notify_info
                tray_icon = self._tray.tray_icon if self._tray else None
                notify_info(
                    tray_icon,
                    "OCR Extraction Complete",
                    f"Copied {len(text)} characters to clipboard.",
                    file_path=None,               # No Open button
                    actions_dict=None,
                    default_action=None,
                    show_open_button=False,
                )
                if self._verbose:
                    print(f"Extracted Text:\n{text}")
            else:
                self._notify_error("Failed to copy OCR text to clipboard")
        else:
            self._notify_error("No text detected in region")
            
        return True

    def capture_color_picker(self) -> bool:
        """Launch the magnifying color picker overlay."""
        logger.info("Starting Color Picker")
        
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False
            
        if backdrop is None or backdrop.isNull():
            return False
            
        from shotx.ui.color_picker import ColorPickerOverlay
        from PySide6.QtCore import QEventLoop
        from PySide6.QtGui import QColor
        
        overlay = ColorPickerOverlay(backdrop)
        loop = QEventLoop()
        
        selected_color: list[QColor] = []
        
        def on_color_selected(color: QColor) -> None:
            selected_color.append(color)
            loop.quit()
            
        def on_cancelled() -> None:
            loop.quit()
            
        overlay.color_selected.connect(on_color_selected)
        overlay.cancelled.connect(on_cancelled)
        
        overlay.showFullScreen()
        loop.exec()
        
        if not selected_color:
            return False
            
        color = selected_color[0]
        hex_str = color.name().upper()
        
        # Copy to clipboard
        from shotx.output.clipboard import copy_text_to_clipboard
        if copy_text_to_clipboard(hex_str):
            from shotx.ui.notification import notify_info
            tray_icon = self._tray.tray_icon if self._tray else None
            notify_info(
                tray_icon,
                "Color Picked",
                f"Copied {hex_str} to clipboard.",
                file_path=None,
                actions_dict=None,
                default_action=None,
                show_open_button=False,
            )
            if self._verbose:
                print(f"Color copied: {hex_str}")
        else:
            self._notify_error("Failed to copy color to clipboard")
            
        return True

    def capture_ruler(self) -> bool:
        """Launch the screen ruler overlay to measure distances."""
        logger.info("Starting Screen Ruler")
        
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False
            
        if backdrop is None or backdrop.isNull():
            return False
            
        from shotx.ui.ruler import RulerOverlay
        from PySide6.QtCore import QEventLoop
        
        overlay = RulerOverlay(backdrop)
        loop = QEventLoop()
        
        def on_cancelled() -> None:
            loop.quit()
            
        overlay.cancelled.connect(on_cancelled)
        
        overlay.show_fullscreen()
        loop.exec()
        
        return True

    def capture_qr_scan(self) -> bool:
        """Select a region and scan it for a QR code."""
        logger.info("Starting QR scan capture")
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        from shotx.ui.overlay import RegionOverlay
        from PySide6.QtCore import QEventLoop, QRect

        overlay = RegionOverlay(backdrop, after_capture_action="capture")
        loop = QEventLoop()

        selected_region = []

        def on_region_selected(rect: QRect) -> None:
            selected_region.append(rect)
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        overlay.region_selected.connect(on_region_selected)
        overlay.selection_cancelled.connect(on_cancelled)

        overlay.show_fullscreen()
        loop.exec()

        if not selected_region:
            return False

        rect = selected_region[0]
        if rect.width() < 2 or rect.height() < 2:
            return False

        # Crop image
        cropped = backdrop.copy(rect)

        # Run QR scan
        from shotx.tools.qr import scan_qr, ZBarError
        try:
            text = scan_qr(cropped)
        except ZBarError as e:
            self._notify_error(str(e))
            return False
        except Exception as e:
            logger.error("QR scan failed: %s", e)
            self._notify_error(f"QR Scan Exception: {e}")
            return False

        if text:
            from shotx.output.clipboard import copy_text_to_clipboard
            if copy_text_to_clipboard(text):
                from shotx.ui.notification import notify_info
                tray_icon = self._tray.tray_icon if self._tray else None
                notify_info(
                    tray_icon,
                    "QR Code Scanned",
                    f"Decoded text copied to clipboard:\n{text[:50]}{'...' if len(text) > 50 else ''}",
                    show_open_button=False,
                )
            else:
                self._notify_error("Failed to copy decoded text to clipboard")
        else:
            self._notify_error("No QR code detected in region")

        return True

    def generate_qr_from_clipboard(self) -> bool:
        """Read clipboard and generate a QR code from it."""
        from shotx.output.clipboard import get_text_from_clipboard
        text = get_text_from_clipboard()

        if not text:
            self._notify_error("Clipboard is empty or does not contain text.")
            return False

        from shotx.tools.qr import generate_qr
        try:
            qimg = generate_qr(text)
        except Exception as e:
            logger.error("QR generation failed: %s", e)
            self._notify_error(f"QR Generation Error: {e}")
            return False

        if not qimg or qimg.isNull():
            return False

        # Copy the generated QR image to clipboard
        from shotx.output.clipboard import copy_image_to_clipboard
        copy_image_to_clipboard(qimg)

        # Notify the user
        from shotx.ui.notification import notify_info
        tray_icon = self._tray.tray_icon if self._tray else None
        notify_info(
            tray_icon,
            "QR Code Generated",
            f"Image copied to clipboard.\nContent: {text[:40]}{'...' if len(text) > 40 else ''}",
            show_open_button=False,
        )

        from shotx.ui.qr_display import QRDisplayOverlay
        self._qr_overlay = QRDisplayOverlay(qimg, text)
        self._qr_overlay.show()
        return True

    def open_hash_checker(self, exec_dialog: bool = False) -> bool:
        """Open the hash checker tool dialog."""
        from shotx.ui.hash_dialog import HashDialog

        self._hash_dialog = HashDialog()
        if exec_dialog:
            self._hash_dialog.exec()
        else:
            self._hash_dialog.show()
        return True

    def open_directory_indexer(self, start_path: str = "", exec_dialog: bool = False) -> bool:
        """Open the directory indexer tool dialog."""
        from shotx.ui.directory_indexer import DirectoryIndexerDialog

        self._indexer_dialog = DirectoryIndexerDialog(initial_dir=start_path)
        if exec_dialog:
            self._indexer_dialog.exec()
        else:
            self._indexer_dialog.show()
        return True

    def open_image_editor(self, initial_image_path: str = "", exec_loop: bool = False) -> bool:
        """Open the full image editor."""
        from shotx.ui.editor import ImageEditorWindow
        from PySide6.QtGui import QImage

        initial_image = None
        if initial_image_path:
            initial_image = QImage(initial_image_path)
            
        self._image_editor = ImageEditorWindow(initial_image=initial_image)
        self._image_editor.show()
        
        # Since ImageEditorWindow is a QMainWindow, we need to manually spin an event loop
        # if this is called from the CLI oneshot mode, otherwise the processes exits instantly.
        if exec_loop:
            from PySide6.QtCore import QEventLoop
            loop = QEventLoop()
            
            # Trap the window close event to unblock CLI
            original_closeEvent = self._image_editor.closeEvent
            def new_closeEvent(event):
                loop.quit()
                original_closeEvent(event)
            self._image_editor.closeEvent = new_closeEvent
            
            loop.exec()

        return True

    def pin_region(self) -> bool:
        """Capture a region and pin it to the screen."""
        logger.info("Starting Pin to Screen capture")
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            self._notify_error(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        from shotx.ui.overlay import RegionOverlay
        from PySide6.QtCore import QEventLoop, QRect
        from PySide6.QtGui import QPixmap

        overlay = RegionOverlay(backdrop, after_capture_action="capture")
        loop = QEventLoop()
        selected_region = []

        def on_region_selected(rect: QRect) -> None:
            selected_region.append(rect)
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        overlay.region_selected.connect(on_region_selected)
        overlay.selection_cancelled.connect(on_cancelled)
        overlay.show_fullscreen()
        loop.exec()

        if not selected_region:
            return False

        rect = selected_region[0]
        if rect.width() < 2 or rect.height() < 2:
            return False

        # Crop image and pin it
        cropped_img = backdrop.copy(rect)
        pixmap = QPixmap.fromImage(cropped_img)
        
        from shotx.ui.pinned import PinnedWidget
        
        # We need to keep a reference to prevent garbage collection
        if not hasattr(self, "_pinned_widgets"):
            self._pinned_widgets = []
            
        pinned = PinnedWidget(pixmap)
        pinned.show()
        self._pinned_widgets.append(pinned)
        
        # Cleanup closed widgets periodically
        pinned.destroyed.connect(lambda: self._pinned_widgets.remove(pinned) if pinned in self._pinned_widgets else None)
        
        return True

    def scan_qr_from_clipboard(self) -> bool:
        """Read image from clipboard and scan it for a QR code."""
        from shotx.output.clipboard import get_image_from_clipboard
        img = get_image_from_clipboard()

        if not img or img.isNull():
            self._notify_error("Clipboard is empty or does not contain an image.")
            return False

        from shotx.tools.qr import scan_qr, ZBarError
        try:
            text = scan_qr(img)
        except ZBarError as e:
            self._notify_error(str(e))
            return False
        except Exception as e:
            logger.error("QR scan from clipboard failed: %s", e)
            self._notify_error(f"QR Scan Error: {e}")
            return False

        if text:
            from shotx.output.clipboard import copy_text_to_clipboard
            if copy_text_to_clipboard(text):
                from shotx.ui.notification import notify_info
                tray_icon = self._tray.tray_icon if self._tray else None
                notify_info(
                    tray_icon,
                    "QR Code Scanned (Clipboard)",
                    f"Decoded text copied to clipboard:\n{text[:50]}{'...' if len(text) > 50 else ''}",
                    show_open_button=False,
                )
            else:
                self._notify_error("Failed to copy decoded text to clipboard")
        else:
            self._notify_error("No QR code detected in clipboard image")

        return True

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
        workflow = self.settings.workflow

        if workflow.save_to_file:
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
                
                # Add to history
                try:
                    size_bytes = Path(saved_path).stat().st_size
                except OSError:
                    size_bytes = 0
                self._history_manager.add_record(
                    filepath=saved_path, 
                    size_bytes=size_bytes, 
                    capture_type=capture_type
                )
                
                # Notify UI components that a new record was saved
                self.capture_saved.emit(saved_path, size_bytes, capture_type)
                
                if self._verbose:
                    print(f"Saved to {saved_path}")
            else:
                logger.warning("Failed to save screenshot to file")

        if workflow.copy_to_clipboard:
            success = copy_image_to_clipboard(image)
            if self._verbose and success:
                print("Copied image to clipboard")

        # Open in editor if enabled and a file was saved
        if workflow.open_in_editor and saved_path:
            self.open_image_editor(saved_path)

        # Kick off upload in the background if enabled and we actually saved a file
        if workflow.upload_image and saved_path:
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
        elif uploader_target == "imgur":
            return ImgurUploader(
                client_id=self.settings.upload.imgur.client_id,
                access_token=self.settings.upload.imgur.access_token,
            )
        else:
            # Default to Tmpfiles.org
            return TmpfilesUploader()

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

    @Slot(str)
    def _on_upload_started(self, file_path: str) -> None:
        # Optional: Show an "Uploading..." notification here, 
        # but ShareX usually is silent until it succeeds to avoid spam.
        if self._verbose:
            print(f"Began background upload for: {file_path}")

    @Slot(str, str)
    def _on_upload_success(self, file_path: str, url: str) -> None:
        """Called by the background thread when upload finishes cleanly."""
        
        # Interceptor: If URL shortener is enabled, pipe it through another worker
        if self.settings.upload.shortener.enabled:
            provider = self.settings.upload.shortener.provider
            if self._verbose:
                print(f"Shortening URL via {provider}...")
                
            shortener = ShortenerWorker(url, provider)
            shortener.signals.success.connect(lambda short_url: self._finalize_upload_success(file_path, short_url))
            self._thread_pool.start(shortener)
        else:
            self._finalize_upload_success(file_path, url)
            
    def _finalize_upload_success(self, file_path: str, final_url: str) -> None:
        """Final step of upload: clipboard and notification."""
        # Update URL in history database
        self._history_manager.update_url_by_path(file_path, final_url)
        
        # Notify UI components that a record was updated (e.g. HistoryWidget)
        self.capture_updated.emit(file_path)

        if self.settings.upload.copy_url_to_clipboard:
            copy_text_to_clipboard(final_url)
            if self._verbose:
                print(f"Copied URL to clipboard: {final_url}")
            
        if self.settings.capture.show_notification:
            tray_icon = self._tray.tray_icon if self._tray else None
            
            # Create a multi-action Split Button array
            actions = {
                "📂 View Local": file_path,
                "🌐 Open Link": final_url
            }
            
            # Map the default body click specifically to the Local File
            notify_info(
                tray_icon=tray_icon, 
                title="Upload Successful", 
                message=f"Link copied to clipboard:\n{final_url}", 
                actions_dict=actions,
                default_action=file_path
            )
            
    @Slot(str, str)
    def _on_upload_error(self, file_path: str, error_msg: str) -> None:
        """Called by the background thread on upload failure."""
        # Because Qt's QSystemTrayIcon cannot distinguish WHICH stacked notification
        # was clicked by the user, we must combine the Error state and the Saved state
        # into a single notification. This allows them to see the error, see the path,
        # AND click the notification to open the local file.
        # GNOME often collapses single newlines in notification bodies, so we force double newlines
        combined_msg = f"{error_msg.strip()}\n\n↳ Fallback local save:\n{file_path}"
        
        tray_icon = self._tray.tray_icon if self._tray else None
        
        # Route this through our central notify_error pipeline so it uses native DBus!
        # Pass the Path(file_path) so the Notification becomes clickable as a fallback
        notify_error(tray_icon, combined_msg, file_path=Path(file_path))
            
        if self._verbose:
            print(f"Upload Error: {error_msg}")

    def run_tray(self) -> int:
        """Run ShotX as a system tray application.

        Returns:
            Exit code (0 = success).
        """
        import signal
        
        # FIX: PySide6 completely masks Python SIGINTs (Ctrl+C) while deep inside the C++ 
        # event loop. Restoring the default signal handler forces immediate termination.
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        init_notifications()
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
        success = False
        if capture_type == "fullscreen":
            success = self.capture_fullscreen()
        elif capture_type == "region":
            success = self.capture_region()
        elif capture_type == "window":
            # Window capture uses the same overlay — user clicks a window
            success = self.capture_region()
        elif capture_type == "ocr":
            success = self.capture_ocr()
        elif capture_type == "color_picker":
            success = self.capture_color_picker()
        elif capture_type == "ruler":
            success = self.capture_ruler()
        elif capture_type == "qr_scan":
            success = self.capture_qr_scan()
        elif capture_type == "qr_generate":
            success = self.generate_qr_from_clipboard()
        elif capture_type == "qr_scan_clipboard":
            success = self.scan_qr_from_clipboard()
        elif capture_type == "pin_region":
            success = self.pin_region()
        elif capture_type == "hash":
            success = self.open_hash_checker(exec_dialog=True)
        elif capture_type == "index_dir":
            # Extract start_path if it was passed via kwargs
            start_path = kwargs.get("start_path", "")
            success = self.open_directory_indexer(start_path, exec_dialog=True)
        elif capture_type == "edit":
            image_path = kwargs.get("image_path", "")
            success = self.open_image_editor(image_path, exec_loop=True)
        elif capture_type == "history":
            success = self.open_history_viewer(exec_dialog=True)
        else:
            print(f"Unknown capture type: {capture_type}")
            return 1

        # Because one-shot mode exits instantly, any background QRunnable 
        # (like UploadWorker) will be brutally killed by the OS.
        # We must wait for the thread pool to drain before returning.
        if success and self._thread_pool.activeThreadCount() > 0:
            if self._verbose:
                print("Waiting for background uploads to finish...")
                
            import time
            from PySide6.QtWidgets import QApplication
            
            app = QApplication.instance()
            start_time = time.time()
            
            # We CANNOT use self._thread_pool.waitForDone() because it blocks
            # the main thread. If the main thread is blocked, it cannot process
            # the Qt Signals emitted by the background worker (like success/error).
            # So the worker finishes, emits success, but the main thread never 
            # triggers the URL clipboard copy because it's sleeping.
            # Instead, we spin the Qt Event Loop until threads finish or timeout.
            while self._thread_pool.activeThreadCount() > 0:
                if time.time() - start_time > 30.0:
                    if self._verbose:
                        print("Background upload timed out.")
                    break
                if app:
                    app.processEvents()
                time.sleep(0.05)

        return 0 if success else 1

    def shorten_clipboard_url(self) -> None:
        """Read URL from clipboard and shorten it."""
        from PySide6.QtWidgets import QApplication
        import re

        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()

        if not text:
            self._notify_error("Clipboard is empty.")
            return

        # Very basic URL check
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", text):
            self._notify_error("Clipboard does not contain a valid URL.")
            return

        provider = self.settings.upload.shortener.provider
        logger.info("Shortening clipboard URL via %s", provider)

        from shotx.upload.shortener import ShortenerWorker
        shortener = ShortenerWorker(text, provider)

        def _on_success(short_url: str) -> None:
            clipboard.setText(short_url)
            self._notify_info("URL Shortened", f"Copied to clipboard:\n{short_url}")

        def _on_error(err_msg: str) -> None:
            self._notify_error(f"URL Shortener failed:\n{err_msg}")

        shortener.signals.success.connect(_on_success)
        shortener.signals.error.connect(_on_error)
        self._thread_pool.start(shortener)

    def open_main_window(self) -> None:
        """Open (or raise) the unified ShotX Main Window."""
        logger.info("Opening Main Window")
        from PySide6.QtCore import Qt
        from shotx.ui.main_window import ShotXMainWindow

        if not hasattr(self, '_main_window') or self._main_window is None:
            self._main_window = ShotXMainWindow(self)

        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def open_history_viewer(self, exec_dialog: bool = False) -> bool:
        """Open the History viewer.

        In tray mode, opens the Main Window (which embeds the history table).
        In CLI oneshot mode, opens the standalone HistoryDialog.
        """
        logger.info("Opening History Viewer")

        # In tray mode, delegate to the Main Window
        if not exec_dialog and self._tray:
            self.open_main_window()
            return True

        # In CLI one-shot mode, use the standalone dialog wrapper
        from shotx.ui.history import HistoryDialog
        dialog = HistoryDialog(self)
        dialog.exec()
        return True

    # --- Private methods ---

    def _setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        level = logging.DEBUG if self._verbose else logging.WARNING
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        # Silence extremely noisy third-party debug loggers
        if self._verbose:
            logging.getLogger("httpcore").setLevel(logging.INFO)
            logging.getLogger("httpx").setLevel(logging.INFO)
            logging.getLogger("asyncio").setLevel(logging.INFO)

    def _notify_error(self, message: str) -> None:
        """Show error via notification or stderr."""
        self._last_notification_type = "error"
        tray_icon = self._tray.tray_icon if self._tray else None
        notify_error(tray_icon, message)
        if self._verbose:
            print(f"Error: {message}", file=sys.stderr)
