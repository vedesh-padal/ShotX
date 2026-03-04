"""XDG desktop utilities (file/folder opening).

Previously these lived inside ``ui/notification.py`` and were duplicated
in ``ui/history.py``.  They are pure OS helpers with no UI dependencies,
so they belong in the core layer.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def open_file(file_path: Path | str) -> bool:
    """Open a file with the default application via ``xdg-open``.

    Works on all FreeDesktop-compliant Linux desktop environments.

    Returns:
        ``True`` if the command was launched, ``False`` on error.
    """
    try:
        subprocess.Popen(
            ["xdg-open", str(file_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        logger.error("xdg-open not found — cannot open file: %s", file_path)
        return False


def open_folder(file_path: Path | str) -> bool:
    """Open the containing folder in the default file manager.

    If *file_path* is a file, opens its parent directory.
    If it is already a directory, opens that directory directly.

    Returns:
        ``True`` if the command was launched, ``False`` on error.
    """
    path = Path(file_path)
    folder = path.parent if path.is_file() else path
    try:
        subprocess.Popen(
            ["xdg-open", str(folder)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        logger.error("xdg-open not found — cannot open folder: %s", folder)
        return False
