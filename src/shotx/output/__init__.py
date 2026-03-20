"""Output handlers for ShotX (clipboard, file saving)."""

from shotx.output.clipboard import copy_image_to_clipboard, copy_text_to_clipboard
from shotx.output.file_saver import expand_filename_pattern, save_image

__all__ = [
    "copy_image_to_clipboard",
    "copy_text_to_clipboard",
    "save_image",
    "expand_filename_pattern",
]
