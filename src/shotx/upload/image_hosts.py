"""Imgur and ImgBB Uploader Implementations."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import mimetypes

from .base import UploaderBackend, UploadError

logger = logging.getLogger(__name__)

# Fallback anonymous Client-ID for ShotX out-of-the-box experience
DEFAULT_IMGUR_CLIENT_ID = "c5b2a0c6a84d2b2"


class ImgurUploader(UploaderBackend):
    """Uploads images to Imgur via their public REST API."""

    def __init__(self, client_id: str | None = None, access_token: str | None = None):
        """Initialize with optional user credentials.

        Args:
            client_id: The user's personal Imgur Client-ID.
            access_token: The user's OAuth access token (highest priority).
        """
        self.client_id = client_id or DEFAULT_IMGUR_CLIENT_ID
        self.access_token = access_token

    def upload(self, file_path: Path) -> str:
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")

        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        else:
            headers["Authorization"] = f"Client-ID {self.client_id}"

        logger.info("Uploading %s to Imgur...", file_path.name)

        try:
            mime_type, _ = mimetypes.guess_type(file_path.name)
            content_type = mime_type or "application/octet-stream"
            
            with open(file_path, "rb") as f:
                # Imgur expects the 'image' field in multipart/form-data
                files = {"image": (file_path.name, f, content_type)}
                
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        "https://api.imgur.com/3/image",
                        headers=headers,
                        files=files,
                    )
        except httpx.RequestError as e:
            raise UploadError(f"Network error while uploading to Imgur: {e}")

        # Handle rate limiting explicitly
        if response.status_code == 429:
            raise UploadError("Imgur rate limit exceeded. Please configure a personal API key in settings.")

        try:
            data = response.json()
        except ValueError:
            raise UploadError(f"Invalid JSON response from Imgur: {response.text[:100]}")

        if not response.is_success:
            err_msg = data.get("data", {}).get("error", "Unknown Imgur error")
            raise UploadError(f"Imgur API Error ({response.status_code}): {err_msg}")

        link = data.get("data", {}).get("link")
        if not link:
            raise UploadError("Imgur API succeeded but returned no image link.")

        logger.info("Imgur upload successful: %s", link)
        return link


class ImgBBUploader(UploaderBackend):
    """Uploads images to ImgBB via their REST API.
    
    ImgBB does not support anonymous client IDs for apps; users MUST provide
    their own API key from https://api.imgbb.com/
    """

    def __init__(self, api_key: str | None = None):
        if not api_key:
            raise UploadError("ImgBB requires a personal API Key in settings. Get one at https://api.imgbb.com/")
        self.api_key = api_key

    def upload(self, file_path: Path) -> str:
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")

        logger.info("Uploading %s to ImgBB...", file_path.name)

        try:
            mime_type, _ = mimetypes.guess_type(file_path.name)
            content_type = mime_type or "application/octet-stream"
            
            with open(file_path, "rb") as f:
                # ImgBB expects the 'image' field and key as query/form param
                files = {"image": (file_path.name, f, content_type)}
                data = {"key": self.api_key}
                
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        "https://api.imgbb.com/1/upload",
                        data=data,
                        files=files,
                    )
        except httpx.RequestError as e:
            raise UploadError(f"Network error while uploading to ImgBB: {e}")

        try:
            # ImgBB returns HTTP 200 even for some errors, must check JSON payload
            payload = response.json()
        except ValueError:
            raise UploadError(f"Invalid JSON response from ImgBB: {response.text[:100]}")

        if not payload.get("success", False):
            err_msg = payload.get("error", {}).get("message", "Unknown ImgBB error")
            status_code = payload.get("status", response.status_code)
            raise UploadError(f"ImgBB API Error ({status_code}): {err_msg}")

        link = payload.get("data", {}).get("url")
        if not link:
            raise UploadError("ImgBB API succeeded but returned no image URL.")

        logger.info("ImgBB upload successful: %s", link)
        return link
