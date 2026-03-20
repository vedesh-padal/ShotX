"""File saving for ShotX.

Saves captured images to disk with configurable naming patterns,
output directory, and image format/quality.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)

# Supported formats and their Qt format strings
FORMAT_MAP: dict[str, str] = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
}


def expand_filename_pattern(
    pattern: str,
    capture_type: str = "fullscreen",
    counter: int = 1,
) -> str:
    """Expand a filename pattern with dynamic variables.

    Supported variables:
        {date}    — current date as YYYY-MM-DD
        {time}    — current time as HH-MM-SS
        {datetime} — YYYY-MM-DD_HH-MM-SS
        {type}    — capture type (fullscreen, region, window)
        {counter} — incrementing counter
        {timestamp} — Unix timestamp

    Args:
        pattern: Filename pattern with {variable} placeholders.
        capture_type: Type of capture performed.
        counter: Sequential counter value.

    Returns:
        Expanded filename string (without extension).
    """
    now = datetime.now()

    replacements = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H-%M-%S"),
        "datetime": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "type": capture_type,
        "counter": str(counter).zfill(4),
        "timestamp": str(int(now.timestamp())),
    }

    result = pattern
    for key, value in replacements.items():
        result = result.replace(f"{{{key}}}", value)

    return result


def save_image(
    image: QImage,
    output_dir: str,
    filename_pattern: str = "ShotX_{date}_{time}",
    image_format: str = "png",
    jpeg_quality: int = 95,
    capture_type: str = "fullscreen",
) -> Path | None:
    """Save a QImage to disk.

    Args:
        image: The captured image.
        output_dir: Directory to save to (~ and env vars expanded).
        filename_pattern: Filename pattern with {variable} placeholders.
        image_format: Output format (png, jpg, jpeg, webp).
        jpeg_quality: Quality for JPEG/WebP (1-100).
        capture_type: Type of capture (for filename pattern).

    Returns:
        Path to the saved file, or None if save failed.
    """
    if image.isNull():
        logger.error("Cannot save a null image")
        return None

    # Expand and create output directory
    expanded_dir = os.path.expanduser(os.path.expandvars(output_dir))
    dir_path = Path(expanded_dir)

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create output directory '%s': %s", dir_path, e)
        return None

    # Build filename
    fmt = image_format.lower()
    if fmt not in FORMAT_MAP:
        logger.error("Unsupported image format: %s", fmt)
        return None

    filename = expand_filename_pattern(
        filename_pattern,
        capture_type=capture_type,
    )
    extension = "jpg" if fmt == "jpeg" else fmt
    file_path = dir_path / f"{filename}.{extension}"

    # Avoid overwriting — append counter if file exists
    if file_path.exists():
        counter = 1
        while file_path.exists():
            file_path = dir_path / f"{filename}_{counter}.{extension}"
            counter += 1

    # Save
    qt_format = FORMAT_MAP[fmt]
    quality = jpeg_quality if fmt in ("jpg", "jpeg", "webp") else -1  # -1 = default for PNG

    try:
        success = image.save(str(file_path), qt_format, quality)  # type: ignore[call-overload]
        if not success:
            logger.error("QImage.save() returned False for '%s'", file_path)
            return None

        logger.info("Screenshot saved: %s (%dx%d)", file_path, image.width(), image.height())
        return file_path

    except Exception as e:
        logger.error("Failed to save image to '%s': %s", file_path, e)
        return None
