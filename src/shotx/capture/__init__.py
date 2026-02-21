"""Screen capture backends for ShotX."""

from shotx.capture.backend import CaptureBackend, MonitorInfo, WindowInfo
from shotx.capture.factory import create_capture_backend, detect_session_type

__all__ = [
    "CaptureBackend",
    "MonitorInfo",
    "WindowInfo",
    "create_capture_backend",
    "detect_session_type",
]
