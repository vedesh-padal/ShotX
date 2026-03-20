"""Qt Background Worker for Uploading.

Because HTTP uploads to Imgur or S3 can take several seconds,
running them on the main thread would freeze the UI and the system tray.
This module provides a QRunnable/QThreadPool mechanism to run the
upload in the background and emit signals back to the main GUI thread.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from .base import UploaderBackend, UploadError

logger = logging.getLogger(__name__)


class UploadSignals(QObject):
    """Defines signals for the background upload worker."""
    started = Signal(str)  # filepath str
    success = Signal(str, str)  # filepath str, url str
    error = Signal(str, str)  # filepath str, error message str


class UploadWorker(QRunnable):
    """Background worker to execute UploaderBackend.

    Must be executed via QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, uploader: UploaderBackend, file_path: Path):
        super().__init__()
        self.uploader = uploader
        self.file_path = file_path
        # QRunnable isn't a QObject, so we use a separate class for signals
        self.signals = UploadSignals()

    def run(self) -> None:
        """Executed in the background thread."""
        self.signals.started.emit(str(self.file_path))
        try:
            url = self.uploader.upload(self.file_path)
            self.signals.success.emit(str(self.file_path), url)
        except UploadError as e:
            logger.error("UploadFailed: %s", e)
            self.signals.error.emit(str(self.file_path), str(e))
        except Exception as e:
            logger.exception("Unexpected error during upload")
            self.signals.error.emit(str(self.file_path), f"Unexpected error: {e}")
