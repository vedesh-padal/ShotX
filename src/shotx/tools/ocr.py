"""OCR tool integration using Tesseract.

Provides simple extraction of text from QImage objects.
Designed to degrade gracefully if Tesseract is not installed on the host OS.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)

class TesseractNotFoundError(Exception):
    """Raised when the tesseract executable cannot be found."""
    pass


def extract_text(image: QImage) -> str:
    """Extract text from a QImage using Tesseract OCR.

    Raises:
        TesseractNotFoundError: If pytesseract fails to find the engine.
        Exception: If OCR processing strictly fails.
    """
    import pytesseract  # type: ignore[import-untyped]
    from pytesseract import TesseractNotFoundError as PyTessError  # type: ignore[import-untyped]

    # We must save QImage to a temporary PNG file because PyTesseract
    # expects either a file path, raw bytes, or a PIL Image.
    # Saving to a tempfile is the most robust bridge.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path = Path(tmp.name)

    try:
        # Save QImage to disk natively
        if not image.save(str(temp_path), "PNG"): # type: ignore[call-overload]
            raise RuntimeError("Failed to save temporary image for OCR processing.")

        text = pytesseract.image_to_string(str(temp_path))
        from typing import cast
        return cast(str, text.strip())

    except PyTessError as e:
        logger.error("Tesseract engine not found: %s", e)
        raise TesseractNotFoundError("Tesseract OS dependency is missing.") from e
    finally:
        # Clean up the temporary image
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
