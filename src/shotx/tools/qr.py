"""QR Code scanning and generation tools."""

from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image
from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)

class ZBarError(Exception):
    """Raised when pyzbar fails or zbar library is missing."""
    pass

def scan_qr(qimage: QImage) -> str | None:
    """Scan a QR code from a QImage and return the decoded text."""
    try:
        from pyzbar.pyzbar import decode
    except ImportError as e:
        logger.error("pyzbar not installed or zbar shared library missing")
        raise ZBarError("The 'pyzbar' library or system 'libzbar0' is missing.") from e

    # Convert QImage to PIL Image
    # qimage.constBits() returns a memoryview of the buffer
    # QImage format is often Format_ARGB32 (4 bytes)
    # PIL expects "RGBA" or similar
    # Using BytesIO and save as temp PNG is often safer for format conversion
    # but let's try direct conversion if possible.

    # Simpler: convert QImage to PNG in memory then to PIL
    from PySide6.QtCore import QBuffer, QIODevice
    qbuffer = QBuffer()
    qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
    qimage.save(qbuffer, "PNG")  # type: ignore[call-overload]

    ba = qbuffer.data()
    pil_img = Image.open(BytesIO(bytes(ba)))

    decoded_objects = decode(pil_img)
    if not decoded_objects:
        return None

    # Return the data of the first QR code found
    return str(decoded_objects[0].data.decode("utf-8"))

def generate_qr(text: str) -> QImage:
    """Generate a QR code QImage from the given text."""
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert PIL image to QImage
    byte_io = BytesIO()
    img.save(byte_io, format="PNG")

    qimg = QImage.fromData(byte_io.getvalue())
    return qimg
