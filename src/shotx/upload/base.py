"""Uploader backend architecture.

Defines the abstract base class and common configuration structures
for all uploaders in the ShotX ecosystem.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when an upload fails."""
    pass


class UploaderBackend(ABC):
    """Base class for all upload plugins (Imgur, S3, FTP, Custom)."""

    @abstractmethod
    def upload(self, file_path: Path) -> str:
        """Upload a file and return the public URL.

        This method MUST be thread-safe as it will be called from a
        QRunnable/QThread background worker to prevent GUI freezing.

        Args:
            file_path: Path to the local file to upload.

        Returns:
            The public, sharable HTTP URL of the uploaded file.

        Raises:
            UploadError: If the upload fails due to network, auth, or API limits.
        """
        pass
