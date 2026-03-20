"""Capture controller.

Owns all capture workflows: fullscreen, region, OCR, color picker, ruler,
QR scan/generate, pin-to-screen, screen recording, and the shared
save-and-notify pipeline.

Extracted from the former god-class ``ShotXApp`` in ``app.py``.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from PySide6.QtCore import QEventLoop, QObject, QRect, QTimer, Slot
from PySide6.QtGui import QColor, QImage, QPixmap

from shotx.capture import CaptureBackend, create_capture_backend
from shotx.capture.recorder import ScreenRecorder
from shotx.capture.region_detect import build_detect_regions
from shotx.config.settings import SettingsManager
from shotx.core.events import event_bus
from shotx.db.history import HistoryManager
from shotx.output.clipboard import (
    copy_image_to_clipboard,
    copy_text_to_clipboard,
    get_image_from_clipboard,
    get_text_from_clipboard,
)
from shotx.output.file_saver import expand_filename_pattern, save_image
from shotx.ui.notification import notify_capture_success, notify_info

logger = logging.getLogger(__name__)


class CaptureController(QObject):
    """Manages all capture workflows and the save/notify pipeline.

    Listens to ``event_bus.capture_requested`` and dispatches to the
    appropriate capture method.
    """

    def __init__(
        self,
        settings_manager: SettingsManager,
        history_manager: HistoryManager,
        *,
        verbose: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings_manager
        self._history = history_manager
        self._verbose = verbose

        self._backend: CaptureBackend | None = None
        self._recorder = ScreenRecorder()
        self._current_recording_format = "mp4"
        self.last_saved_path: str | None = None

        # Pinned widgets need to survive GC
        self._pinned_widgets: list = []
        # QR overlay reference
        self._qr_overlay = None

        # Wire EventBus
        event_bus.capture_requested.connect(self._on_capture_requested)
        event_bus.pin_image_requested.connect(self.pin_image_from_file)
        event_bus.start_recording_requested.connect(self.start_recording)
        event_bus.stop_recording_requested.connect(self.stop_recording)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def settings(self):
        return self._settings.settings

    @property
    def backend(self) -> CaptureBackend:
        if self._backend is None:
            self._backend = create_capture_backend()
        return self._backend

    # ------------------------------------------------------------------
    # EventBus dispatcher
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_capture_requested(self, capture_type: str) -> None:
        from collections.abc import Callable
        dispatch: dict[str, Callable] = {
            "fullscreen": self.capture_fullscreen,
            "region": self.capture_region,
            "window": self.capture_region,
            "ocr": self.capture_ocr,
            "color_picker": self.capture_color_picker,
            "ruler": self.capture_ruler,
            "qr_scan": self.capture_qr_scan,
            "qr_generate": self.generate_qr_from_clipboard,
            "qr_scan_clipboard": self.scan_qr_from_clipboard,
            "pin_region": self.pin_region,
        }
        handler = dispatch.get(capture_type)
        if handler:
            handler()
        else:
            logger.warning("Unknown capture type: %s", capture_type)

    # ------------------------------------------------------------------
    # Capture methods
    # ------------------------------------------------------------------

    def capture_fullscreen(self, monitor_index: int | None = None) -> bool:
        """Capture the full screen, save, and copy to clipboard."""
        logger.info("Capturing fullscreen (monitor=%s)", monitor_index)

        delay_sec = self.settings.capture.screenshot_delay
        if delay_sec > 0:
            logger.info("Waiting %d seconds before fullscreen capture...", delay_sec)
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
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if image is None or image.isNull():
            logger.error("Capture returned no image")
            event_bus.notify_error_requested.emit(
                "Screenshot capture failed — no image returned"
            )
            return False

        if self._verbose:
            print(f"Captured {image.width()}x{image.height()} image")

        return self._save_and_notify(image, capture_type="fullscreen")

    def capture_region(self) -> bool:
        """Capture a user-selected region of the screen."""
        logger.info("Starting region capture")

        delay_sec = self.settings.capture.screenshot_delay
        if delay_sec > 0:
            logger.info("Waiting %d seconds before region capture backdrop...", delay_sec)
            loop = QEventLoop()
            QTimer.singleShot(int(delay_sec * 1000), loop.quit)
            loop.exec()

        try:
            backdrop = self.backend.capture_fullscreen(
                show_cursor=self.settings.capture.show_cursor
            )
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            logger.error("Backdrop capture returned no image")
            event_bus.notify_error_requested.emit(
                "Could not capture screen for region selection"
            )
            return False

        if self._verbose:
            print(f"Backdrop captured: {backdrop.width()}x{backdrop.height()}")

        # Collect detectable regions
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

        # Show overlay
        from shotx.ui.overlay import RegionOverlay

        overlay = RegionOverlay(
            backdrop,
            regions,
            after_capture_action=self.settings.capture.after_capture_action,
            last_annotation_color=self.settings.capture.last_annotation_color,
        )

        def _save_color(hex_color: str) -> None:
            self.settings.capture.last_annotation_color = hex_color
            self._settings.save()

        loop = QEventLoop()
        selected_rect: list[QRect] = []
        annotated_image: list[QImage] = []

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

        loop.exec()

        if annotated_image:
            cropped = annotated_image[0]
        elif selected_rect:
            rect = selected_rect[0]
            if self._verbose:
                print(
                    f"Selected region: {rect.x()},{rect.y()} {rect.width()}x{rect.height()}"
                )
            cropped = backdrop.copy(rect)
        else:
            if self._verbose:
                print("Region selection cancelled")
            return False

        if cropped.isNull():
            logger.error("Failed to crop backdrop to selected region")
            event_bus.notify_error_requested.emit("Failed to crop selected region")
            return False

        return self._save_and_notify(cropped, capture_type="region")

    def capture_ocr(self) -> bool:
        """Capture a region and apply Tesseract OCR to extract text."""
        logger.info("Starting OCR capture")
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        # Region selection overlay
        regions = []
        if self.settings.capture.auto_detect_regions:
            try:
                windows = self.backend.get_windows()
                regions = build_detect_regions(windows, include_atspi=True)
            except Exception:
                pass

        from shotx.ui.overlay import RegionOverlay

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

        from shotx.tools.ocr import TesseractNotFoundError, extract_text

        try:
            text = extract_text(cropped)
        except TesseractNotFoundError:
            event_bus.notify_error_requested.emit(
                "Tesseract missing. Please install 'tesseract-ocr'."
            )
            return False
        except Exception as e:
            logger.error("OCR failed: %s", e)
            event_bus.notify_error_requested.emit(f"OCR Exception: {e}")
            return False

        if text:
            if copy_text_to_clipboard(text):
                notify_info(
                    None,
                    "OCR Extraction Complete",
                    f"Copied {len(text)} characters to clipboard.",
                    show_open_button=False,
                )
                if self._verbose:
                    print(f"Extracted Text:\n{text}")
            else:
                event_bus.notify_error_requested.emit(
                    "Failed to copy OCR text to clipboard"
                )
        else:
            event_bus.notify_error_requested.emit("No text detected in region")

        return True

    def capture_color_picker(self) -> bool:
        """Launch the magnifying color picker overlay."""
        logger.info("Starting Color Picker")
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        from shotx.ui.color_picker import ColorPickerOverlay

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

        hex_str = selected_color[0].name().upper()
        if copy_text_to_clipboard(hex_str):
            notify_info(
                None,
                "Color Picked",
                f"Copied {hex_str} to clipboard.",
                show_open_button=False,
            )
            if self._verbose:
                print(f"Color copied: {hex_str}")
        else:
            event_bus.notify_error_requested.emit("Failed to copy color to clipboard")

        return True

    def capture_ruler(self) -> bool:
        """Launch the screen ruler overlay."""
        logger.info("Starting Screen Ruler")
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        from shotx.ui.ruler import RulerOverlay

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
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        from shotx.ui.overlay import RegionOverlay

        overlay = RegionOverlay(backdrop, after_capture_action="capture")
        loop = QEventLoop()
        selected_region: list[QRect] = []

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

        cropped = backdrop.copy(rect)

        from shotx.tools.qr import ZBarError, scan_qr

        try:
            text = scan_qr(cropped)
        except ZBarError as e:
            event_bus.notify_error_requested.emit(str(e))
            return False
        except Exception as e:
            logger.error("QR scan failed: %s", e)
            event_bus.notify_error_requested.emit(f"QR Scan Exception: {e}")
            return False

        if text:
            if copy_text_to_clipboard(text):
                notify_info(
                    None,
                    "QR Code Scanned",
                    f"Decoded text copied to clipboard:\n{text[:50]}{'...' if len(text) > 50 else ''}",
                    show_open_button=False,
                )
            else:
                event_bus.notify_error_requested.emit(
                    "Failed to copy decoded text to clipboard"
                )
        else:
            event_bus.notify_error_requested.emit("No QR code detected in region")

        return True

    def generate_qr_from_clipboard(self) -> bool:
        """Read clipboard and generate a QR code from it."""
        text = get_text_from_clipboard()
        if not text:
            event_bus.notify_error_requested.emit(
                "Clipboard is empty or does not contain text."
            )
            return False

        from shotx.tools.qr import generate_qr

        try:
            qimg = generate_qr(text)
        except Exception as e:
            logger.error("QR generation failed: %s", e)
            event_bus.notify_error_requested.emit(f"QR Generation Error: {e}")
            return False

        if not qimg or qimg.isNull():
            return False

        copy_image_to_clipboard(qimg)
        notify_info(
            None,
            "QR Code Generated",
            f"Image copied to clipboard.\nContent: {text[:40]}{'...' if len(text) > 40 else ''}",
            show_open_button=False,
        )

        from shotx.ui.qr_display import QRDisplayOverlay

        self._qr_overlay = QRDisplayOverlay(qimg, text)
        self._qr_overlay.show()
        return True

    def scan_qr_from_clipboard(self) -> bool:
        """Read image from clipboard and scan it for a QR code."""
        img = get_image_from_clipboard()
        if not img or img.isNull():
            event_bus.notify_error_requested.emit(
                "Clipboard is empty or does not contain an image."
            )
            return False

        from shotx.tools.qr import ZBarError, scan_qr

        try:
            text = scan_qr(img)
        except ZBarError as e:
            event_bus.notify_error_requested.emit(str(e))
            return False
        except Exception as e:
            logger.error("QR scan from clipboard failed: %s", e)
            event_bus.notify_error_requested.emit(f"QR Scan Error: {e}")
            return False

        if text:
            if copy_text_to_clipboard(text):
                notify_info(
                    None,
                    "QR Code Scanned (Clipboard)",
                    f"Decoded text copied to clipboard:\n{text[:50]}{'...' if len(text) > 50 else ''}",
                    show_open_button=False,
                )
            else:
                event_bus.notify_error_requested.emit(
                    "Failed to copy decoded text to clipboard"
                )
        else:
            event_bus.notify_error_requested.emit(
                "No QR code detected in clipboard image"
            )
        return True

    def pin_region(self) -> bool:
        """Capture a region and pin it to the screen."""
        logger.info("Starting Pin to Screen capture")
        try:
            backdrop = self.backend.capture_fullscreen()
        except Exception as e:
            logger.error("Backdrop capture failed: %s", e)
            event_bus.notify_error_requested.emit(f"Capture failed: {e}")
            return False

        if backdrop is None or backdrop.isNull():
            return False

        from shotx.ui.overlay import RegionOverlay

        overlay = RegionOverlay(backdrop, after_capture_action="capture")
        loop = QEventLoop()
        selected_region: list[QRect] = []

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

        cropped_img = backdrop.copy(rect)
        pixmap = QPixmap.fromImage(cropped_img)

        from shotx.ui.pinned import PinnedWidget

        pinned = PinnedWidget(pixmap)
        pinned.show()
        self._pinned_widgets.append(pinned)
        pinned.destroyed.connect(
            lambda: (
                self._pinned_widgets.remove(pinned)
                if pinned in self._pinned_widgets
                else None
            )
        )
        return True

    @Slot(str)
    def pin_image_from_file(self, filepath: str) -> bool:
        """Load an image from disk and pin it directly without a capture overlay."""
        logger.info("Pinning image from file: %s", filepath)
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            logger.error("Cannot load image for pinning: %s", filepath)
            event_bus.notify_error_requested.emit(f"Cannot load image: {filepath}")
            return False
        from shotx.ui.pinned import PinnedWidget
        pinned = PinnedWidget(pixmap)
        pinned.show()
        self._pinned_widgets.append(pinned)
        pinned.destroyed.connect(
            lambda: (
                self._pinned_widgets.remove(pinned)
                if pinned in self._pinned_widgets
                else None
            )
        )
        return True


    @Slot(str)
    def start_recording(self, recording_format: str = "mp4") -> bool:
        """Start a screen recording session."""
        try:
            self._recorder.check_dependencies()
        except Exception as e:
            event_bus.notify_error_requested.emit(str(e))
            return False

        if self._recorder.is_recording:
            return False

        self._current_recording_format = recording_format

        backdrop = self.backend.capture_fullscreen()
        if not backdrop:
            event_bus.notify_error_requested.emit(
                "Failed to capture screen for region selection"
            )
            return False

        regions = None
        if self.settings.capture.auto_detect_regions:
            try:
                windows = self.backend.get_windows()
                regions = build_detect_regions(windows, include_atspi=True)
            except Exception as e:
                logger.warning("Window enumeration failed: %s", e)
                regions = []

        from shotx.ui.overlay import RegionOverlay

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
        output_dir = Path(self.settings.capture.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{expand_filename_pattern(self.settings.capture.filename_pattern, capture_type='recording')}.mp4"
        output_path = output_dir / filename

        self._recorder.start_recording(output_path, rect)

        if self._verbose:
            print(f"Started recording to {output_path}")
        return True

    @Slot()
    def stop_recording(self) -> bool:
        """Stop the active recording and process files."""
        if not self._recorder.is_recording:
            return False

        video_path = self._recorder.stop_recording()

        if not video_path or not video_path.exists():
            event_bus.notify_error_requested.emit("Failed to save recording")
            return False

        final_path = video_path

        if self._current_recording_format == "gif":
            gif_filename = f"{expand_filename_pattern(self.settings.capture.filename_pattern, capture_type='recording')}.gif"
            gif_path = video_path.parent / gif_filename
            result_path = self._recorder.create_gif_from_video(video_path, gif_path)
            if result_path and result_path.exists():
                with contextlib.suppress(OSError):
                    video_path.unlink()
                final_path = result_path
            else:
                event_bus.notify_error_requested.emit(
                    "Failed to convert recording to GIF"
                )

        self.last_saved_path = str(final_path)

        if self._verbose:
            print(f"Saved recording to {final_path}")

        if self.settings.capture.show_notification:
            notify_capture_success(None, Path(final_path))

        return True

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _save_and_notify(self, image: QImage, capture_type: str = "capture") -> bool:
        """Common pipeline: save → clipboard → upload → notify."""
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
                self.last_saved_path = str(saved_path)
                try:
                    size_bytes = Path(saved_path).stat().st_size
                except OSError:
                    size_bytes = 0
                self._history.add_record(
                    filepath=str(saved_path),
                    size_bytes=size_bytes,
                    capture_type=capture_type,
                )
                event_bus.capture_completed.emit(str(saved_path), size_bytes, capture_type)

                if self._verbose:
                    print(f"Saved to {saved_path}")
            else:
                logger.warning("Failed to save screenshot to file")
        else:
            # We must save to a secure temporary file because uploader and editor need a file
            import os
            import tempfile
            tmp_dir = Path(tempfile.gettempdir()) / "shotx"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_path_str = tempfile.mkstemp(dir=tmp_dir, suffix=".png", prefix="cap_")
            os.close(fd)
            # Use fixed high quality PNG for temp transit
            if image.save(tmp_path_str, "PNG"):  # type: ignore[call-overload]
                saved_path = Path(tmp_path_str)
            else:
                logger.error("Failed to save temporary image to %s", tmp_path_str)

        if workflow.copy_to_clipboard:
            success = copy_image_to_clipboard(image)
            if self._verbose and success:
                print("Copied image to clipboard")

        if workflow.open_in_editor and saved_path:
            event_bus.tool_requested_with_args.emit("editor", {"initial_image_path": str(saved_path)})

        if workflow.upload_image and saved_path:
            event_bus.upload_requested.emit(str(saved_path))
        else:
            if self.settings.capture.show_notification:
                notify_capture_success(None, saved_path)

        return True
