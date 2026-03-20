"""Custom Uploader Parser for ShareX .sxcu files."""

from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, cast

import httpx
from httpx import Response

from .base import UploaderBackend, UploadError

logger = logging.getLogger(__name__)


class SxcuParser:
    """Parses standard ShareX .sxcu JSON configuration files."""

    @classmethod
    def load(cls, file_path: Path) -> dict[str, Any]:
        """Load and validate an .sxcu file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Custom uploader config not found: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise UploadError(f"Failed to parse .sxcu file {file_path.name}: {e}") from e

        # Basic validation
        if "RequestURL" not in data:
            raise UploadError(f"Invalid .sxcu: Missing 'RequestURL' in {file_path.name}")

        return cast("dict[str, Any]", data)


class CustomUploader(UploaderBackend):
    """Executes dynamic HTTP requests based on a ShareX .sxcu definition."""

    def __init__(self, sxcu_data: dict[str, Any]):
        self.config = sxcu_data
        self.name = self.config.get("Name", "Custom Uploader")
        self.request_url = self.config.get("RequestURL", "")
        self.method = self.config.get("RequestMethod", "POST").upper()
        self.headers = self.config.get("Headers", {})
        self.arguments = self.config.get("Arguments", {})
        self.file_form_name = self.config.get("FileFormName", "file")
        self.url_path = self.config.get("URL", "")
        # Deletion properties not implemented for MVP, but ShareX format supports them

    def upload(self, file_path: Path) -> str:
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")

        logger.info("Uploading via Custom Uploader: %s to %s", self.name, self.request_url)

        try:
            mime_type, _ = mimetypes.guess_type(file_path.name)
            content_type = mime_type or "application/octet-stream"

            with open(file_path, "rb") as f:
                # ShareX uses Form data (multipart/form-data) by default for images
                files = {self.file_form_name: (file_path.name, f, content_type)}

                # Any extra form arguments
                data = self.arguments

                with httpx.Client(timeout=30.0) as client:
                    if self.method == "POST":
                        response = client.post(
                            self.request_url,
                            headers=self.headers,
                            data=data,
                            files=files,
                        )
                    elif self.method == "PUT":
                        response = client.put(
                            self.request_url,
                            headers=self.headers,
                            data=data,
                            files=files,
                        )
                    else:
                        raise UploadError(f"Unsupported HTTP method in .sxcu: {self.method}")

        except httpx.RequestError as e:
            raise UploadError(f"Network error in custom uploader '{self.name}': {e}") from e

        # Try to parse the URL out of the response
        if not response.is_success:
            logger.error("Failed custom upload %s: %s", response.status_code, response.text[:200])
            raise UploadError(f"Custom Server Error ({response.status_code}): {response.text[:100]}")

        final_url = self._extract_url(response)

        if not final_url:
             raise UploadError(f"Custom uploader succeeded but failed to parse the resulting URL. Response: {response.text[:100]}")

        logger.info("Custom upload successful: %s", final_url)
        return final_url

    def _extract_url(self, response: Response) -> str:
        """Apply ShareX JSONPath or regex to extract the URL from the response."""

        # If the user didn't specify a way to parse the URL, and the response is
        # just a raw string (like a URL), return it directly.
        if not self.url_path:
            text = response.text.strip()
            if text.startswith("http://") or text.startswith("https://"):
                return text
            return ""

        # The 'URL' field in an sxcu file usually contains JSONPath variables
        # like: {json:data.url} or {json:url} or {response}
        try:
            json_response = response.json()
        except ValueError:
            # Not JSON, maybe it's just meant to be the whole response ({response})
            if "{response}" in self.url_path:
                return cast(str, self.url_path.replace("{response}", response.text.strip()))
            return ""

        # Basic ShareX JSON extraction parser.
        # ShareX syntax looks like $json:status.url$ or {json:data.link}
        # This is a rudimentary string replacement for the most common patterns
        # to avoid pulling in a full JSONPath library dependency for the MVP.

        url_template = self.url_path

        import re
        # Match {json:something} or $json:something$
        matches = re.finditer(r"[{|$\s]json:([a-zA-Z0-9_\.]+)[\s|}|.$]", url_template)

        for match in matches:
            full_tag = match.group(0)
            json_path = match.group(1) # e.g. "data.link"

            # Traverse the JSON dict
            parts = json_path.split(".")
            current_val = json_response
            try:
                for part in parts:
                    if isinstance(current_val, dict):
                        current_val = current_val.get(part)
                    elif isinstance(current_val, list):
                        current_val = current_val[int(part)]
                    else:
                        current_val = None
                        break

                if current_val:
                    url_template = url_template.replace(full_tag, str(current_val))
            except (KeyError, IndexError, ValueError):
                continue

        return cast(str, url_template)
