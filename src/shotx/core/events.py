"""Application-wide event bus using Qt Signals.

The EventBus is the central nervous system of the refactored architecture.
UI components emit signals here; backend controllers listen and react.
This eliminates the need for UI modules to hold a direct reference to the
``ShotXApp`` god-class.

Usage::

    from shotx.core.events import event_bus

    # In a UI component (emitter):
    event_bus.capture_requested.emit("fullscreen")

    # In a controller (listener):
    event_bus.capture_requested.connect(self._on_capture)
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Singleton-style signal hub for cross-component communication.

    All signals are defined here so that any module can import the bus
    without pulling in heavy dependencies (no circular imports).
    """

    # ---- Capture signals ----
    # Emitted by UI when user requests a capture.
    # Payload: capture_type str ("fullscreen", "region", "window")
    capture_requested = Signal(str)

    # Emitted by CaptureController after a successful capture.
    # Payload: (filepath: str, size_bytes: int, capture_type: str)
    capture_completed = Signal(str, int, str)

    # ---- Tool signals ----
    # Emitted by UI to launch a tool.
    # Payload: tool_name str ("editor", "hash", "indexer", "history",
    #          "color_picker", "ruler", "qr_scan", "qr_generate",
    #          "qr_scan_clipboard", "pin_region", "shorten_url")
    tool_requested = Signal(str)

    # Emitted with optional keyword arguments packed into a dict.
    # Payload: (tool_name: str, kwargs: dict)
    tool_requested_with_args = Signal(str, dict)

    # Emitted to pin an existing image file directly (no capture overlay).
    # Payload: filepath str
    pin_image_requested = Signal(str)

    # ---- Upload signals ----
    # Request to start a background upload.
    # Payload: filepath str
    upload_requested = Signal(str)

    # Upload finished successfully.
    # Payload: (filepath: str, url: str)
    upload_completed = Signal(str, str)

    # Upload failed.
    # Payload: (filepath: str, error_msg: str)
    upload_failed = Signal(str, str)

    # ---- Recording signals ----
    start_recording_requested = Signal(str)  # format: "mp4", "webm", "gif"
    stop_recording_requested = Signal()

    # ---- Notification signals ----
    # Controllers emit these instead of calling notification functions directly.
    # Payload: (title: str, message: str)
    notify_info_requested = Signal(str, str)

    # Payload: message str
    notify_error_requested = Signal(str)

    # ---- UI navigation signals ----
    open_main_window_requested = Signal()
    open_settings_requested = Signal(int)  # page index

    # ---- Settings signals ----
    # Emitted after settings are saved so components can refresh.
    settings_changed = Signal()


# Module-level singleton.
# Import this everywhere: ``from shotx.core.events import event_bus``
event_bus = EventBus()
