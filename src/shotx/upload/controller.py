"""Upload controller.

Owns the entire upload lifecycle: uploader factory selection, background
dispatch via TaskManager, URL shortening, and clipboard/notification
post-processing.

Extracted from the former god-class ``ShotXApp`` in ``app.py``.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Slot

from shotx.config.settings import SettingsManager
from shotx.core.events import event_bus
from shotx.core.tasks import task_manager
from shotx.db.history import HistoryManager
from shotx.output.clipboard import copy_text_to_clipboard
from shotx.upload.base import UploaderBackend, UploadError
from shotx.upload.custom import CustomUploader, SxcuParser
from shotx.upload.ftp import FtpUploader, SftpUploader
from shotx.upload.image_hosts import ImgBBUploader, ImgurUploader, TmpfilesUploader
from shotx.upload.s3 import S3Uploader
from shotx.upload.shortener import ShortenerWorker
from shotx.upload.worker import UploadWorker

logger = logging.getLogger(__name__)


class UploadController(QObject):
    """Manages file uploads, URL shortening, and post-upload actions.

    Listens to ``event_bus.upload_requested`` and orchestrates the
    background upload pipeline.
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

        # Wire EventBus
        event_bus.upload_requested.connect(self.start_upload)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @Slot(str)
    def start_upload(self, file_path_str: str) -> None:
        """Begin a background upload for the given file path."""
        file_path = Path(file_path_str)
        try:
            uploader = self._create_uploader()
        except UploadError as e:
            event_bus.notify_error_requested.emit(str(e))
            return

        worker = UploadWorker(uploader, file_path)
        worker.signals.started.connect(self._on_upload_started)
        worker.signals.success.connect(self._on_upload_success)
        worker.signals.error.connect(self._on_upload_error)

        task_manager.submit(worker, tag=f"upload_{file_path.name}")

    def shorten_clipboard_url(
        self, headless: bool = False, url: str | None = None
    ) -> bool:
        """Shorten a URL (from argument or clipboard).

        Args:
            headless: If True, prints to stdout/stderr instead of notifications.
            url: If provided, shortens this URL directly. Otherwise reads clipboard.

        Returns:
            True if the shortening request was dispatched.
        """
        if url is not None:
            text = url.strip()
            source_desc = "Provided URL"
        else:
            from shotx.output.clipboard import get_text_from_clipboard

            text = (get_text_from_clipboard() or "").strip()
            source_desc = "Clipboard"

        if not text:
            msg = f"{source_desc} is empty or does not contain text."
            if headless:
                print(f"Error: {msg}", file=sys.stderr)
            else:
                event_bus.notify_error_requested.emit(msg)
            return False

        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", text):
            msg = f"{source_desc} does not contain a valid URL."
            if headless:
                print(f"Error: {msg}", file=sys.stderr)
            else:
                event_bus.notify_error_requested.emit(msg)
            return False

        settings = self._settings.settings
        provider = settings.upload.shortener.provider
        logger.info("Shortening URL via %s", provider)

        worker = ShortenerWorker(text, provider)

        def _on_success(short_url: str) -> None:
            copy_text_to_clipboard(short_url)
            if headless:
                print(short_url, flush=True)
            else:
                event_bus.notify_info_requested.emit(
                    "URL Shortened", f"Copied to clipboard:\n{short_url}"
                )

        def _on_error(err_msg: str) -> None:
            if headless:
                print(
                    f"Error: URL Shortener failed: {err_msg}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                event_bus.notify_error_requested.emit(
                    f"URL Shortener failed:\n{err_msg}"
                )

        worker.signals.success.connect(_on_success)
        worker.signals.error.connect(_on_error)

        task_manager.submit(worker, tag="shorten_url")
        return True

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _create_uploader(self) -> UploaderBackend:
        """Instantiate the correct uploader backend based on settings."""
        settings = self._settings.settings
        target = settings.upload.default_uploader.lower()

        if target == "imgbb":
            return ImgBBUploader(api_key=settings.upload.imgbb.api_key)
        elif target == "s3":
            c = settings.upload.s3
            return S3Uploader(
                endpoint_url=c.endpoint_url or None,
                access_key=c.access_key,
                secret_key=c.secret_key,
                bucket_name=c.bucket_name,
                public_url_format=c.public_url_format or None,
            )
        elif target == "ftp":
            return FtpUploader(config=settings.upload.ftp)
        elif target == "sftp":
            return SftpUploader(config=settings.upload.sftp)
        elif target.startswith("custom:"):
            sxcu_name = target.split(":", 1)[1]
            from shotx.config.settings import _default_config_dir

            sxcu_dir = Path(_default_config_dir()) / "uploaders"
            sxcu_path = sxcu_dir / f"{sxcu_name}.sxcu"
            try:
                sxcu_data = SxcuParser.load(sxcu_path)
            except FileNotFoundError as e:
                raise UploadError(
                    f"Custom uploader '{sxcu_name}' not found. "
                    f"Make sure '{sxcu_name}.sxcu' exists in {sxcu_dir}"
                ) from e
            return CustomUploader(sxcu_data)
        elif target == "imgur":
            return ImgurUploader(
                client_id=settings.upload.imgur.client_id,
                access_token=settings.upload.imgur.access_token,
            )
        else:
            return TmpfilesUploader()

    @Slot(str)
    def _on_upload_started(self, file_path: str) -> None:
        if self._verbose:
            print(f"Began background upload for: {file_path}")

    @Slot(str, str)
    def _on_upload_success(self, file_path: str, url: str) -> None:
        """Post-upload: optionally shorten, then finalize."""
        settings = self._settings.settings
        if settings.upload.shortener.enabled:
            provider = settings.upload.shortener.provider
            if self._verbose:
                print(f"Shortening URL via {provider}...")
            worker = ShortenerWorker(url, provider)
            worker.signals.success.connect(
                lambda short_url: self._finalize_upload(file_path, short_url)
            )
            worker.signals.error.connect(
                lambda err: logger.error("Upload URL shortening failed: %s", err)
            )
            task_manager.submit(worker, tag=f"shorten_upload_{Path(file_path).name}")
        else:
            self._finalize_upload(file_path, url)

    def _finalize_upload(self, file_path: str, final_url: str) -> None:
        """Final step: update history, copy URL, notify."""
        from shotx.ui.notification import notify_info

        self._history.update_url_by_path(file_path, final_url)
        event_bus.capture_completed.emit(file_path, 0, "upload")

        settings = self._settings.settings
        url_copied = False
        if settings.upload.copy_url_to_clipboard:
            copy_text_to_clipboard(final_url)
            url_copied = True
            if self._verbose:
                print(f"Copied URL to clipboard: {final_url}")

        if settings.capture.show_notification:
            actions = {"📂 View Local": file_path, "🌐 Open Link": final_url}
            if url_copied:
                message = f"Link copied to clipboard:\n{final_url}"
            else:
                message = f"Upload complete:\n{final_url}"
            notify_info(
                tray_icon=None,
                title="Upload Successful",
                message=message,
                actions_dict=actions,
                default_action=file_path,
            )

    @Slot(str, str)
    def _on_upload_error(self, file_path: str, error_msg: str) -> None:
        from shotx.ui.notification import notify_error

        combined_msg = (
            f"{error_msg.strip()}\n\n↳ Fallback local save:\n{file_path}"
        )
        notify_error(None, combined_msg, file_path=Path(file_path))

        if self._verbose:
            print(f"Upload Error: {error_msg}")
