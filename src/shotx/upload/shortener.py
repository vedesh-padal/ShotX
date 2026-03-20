"""URL Shortener Integrations.

Used as a post-upload interceptor to shorten massive S3/FTP URLs
before copying them to the user's clipboard.
"""

from __future__ import annotations

import logging

import httpx
from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


def shorten_url_sync(long_url: str, provider: str = "tinyurl") -> str:
    """Synchronously shortens a URL using public free APIs."""
    provider = provider.lower()

    try:
        if provider == "tinyurl":
            api_url = f"https://tinyurl.com/api-create.php?url={long_url}"
            with httpx.Client(timeout=10.0) as client:
                res = client.get(api_url)
                res.raise_for_status()
                return res.text.strip()

        elif provider == "isgd":
            api_url = f"https://is.gd/create.php?format=simple&url={long_url}"
            with httpx.Client(timeout=10.0) as client:
                res = client.get(api_url)
                res.raise_for_status()
                return res.text.strip()

        elif provider == "vgd":
            api_url = f"https://v.gd/create.php?format=simple&url={long_url}"
            with httpx.Client(timeout=10.0) as client:
                res = client.get(api_url)
                res.raise_for_status()
                return res.text.strip()

        else:
            logger.warning("Unknown URL shortener provider: %s", provider)
            return long_url

    except httpx.RequestError as e:
        logger.error("Failed to shorten URL '%s' via %s: %s", long_url, provider, e)
        # On failure, it is safer to return the long URL rather than breaking the pipe
        return long_url


class ShortenerSignals(QObject):
    success = Signal(str)  # short_url
    error = Signal(str)    # error message


class ShortenerWorker(QRunnable):
    """Background worker to shorten a URL without freezing the GUI."""

    def __init__(self, long_url: str, provider: str):
        super().__init__()
        self.long_url = long_url
        self.provider = provider
        self.signals = ShortenerSignals()

    def run(self) -> None:
        try:
            short_url = shorten_url_sync(self.long_url, self.provider)
            if short_url == self.long_url:
                # shorten_url_sync returns the original URL on failure
                self.signals.error.emit(
                    f"Shortener returned the original URL (provider: {self.provider})"
                )
            else:
                self.signals.success.emit(short_url)
        except Exception as e:
            logger.error("ShortenerWorker failed: %s", e)
            self.signals.error.emit(str(e))
