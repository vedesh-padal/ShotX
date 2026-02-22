"""Hash calculation logic for files and data."""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

def calculate_hashes(data: bytes | str) -> dict[str, str]:
    """Calculate MD5, SHA1, and SHA256 hashes for the given data."""
    if isinstance(data, str):
        data = data.encode("utf-8")

    return {
        "MD5": hashlib.md5(data).hexdigest(),
        "SHA1": hashlib.sha1(data).hexdigest(),
        "SHA256": hashlib.sha256(data).hexdigest(),
    }

def calculate_file_hashes(file_path: str) -> dict[str, str]:
    """Calculate hashes for a file, using streaming to handle large files."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
    except Exception as e:
        logger.error("Failed to read file for hashing: %s", e)
        raise

    return {
        "MD5": md5.hexdigest(),
        "SHA1": sha1.hexdigest(),
        "SHA256": sha256.hexdigest(),
    }
