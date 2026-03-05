# Architecture

ShotX uses an **event-driven architecture** with domain-specific controllers, a central signal hub, and a thin orchestrator.

## Overview

```
main.py (CLI parser)
  └── app.py (DI container / orchestrator)
        ├── CaptureController   ← all capture workflows
        ├── UploadController    ← upload pipeline + URL shortener
        ├── ToolController      ← editor, hash, indexer, history
        ├── EventBus            ← inter-component Qt signals
        ├── TaskManager         ← GC-safe background thread pool
        └── TrayIcon / MainWindow (UI shell)
```

## Core Components

### EventBus (`core/events.py`)

A `QObject` singleton that defines application-wide Qt Signals, grouped by domain:

- **Capture**: `capture_requested`, `capture_completed`
- **Tools**: `tool_requested`, `tool_requested_with_args`
- **Upload**: `upload_requested`
- **Notifications**: `notify_error_requested`, `notify_info_requested`
- **Recording**: `start_recording_requested`, `stop_recording_requested`
- **UI**: `open_main_window_requested`

Components communicate by emitting signals on the EventBus. No component needs a direct reference to any other component.

### TaskManager (`core/tasks.py`)

A lifecycle-safe wrapper around `QThreadPool` that:

- Keeps strong references to active `QRunnable` workers
- Prevents garbage collection of signal closures while workers are running
- Automatically cleans up references when workers complete

### Platform Utils (`core/platform.py`)

Centralized Wayland/X11 detection with `lru_cache`:

- `session_type() -> str` — returns `"wayland"`, `"x11"`, or `"unknown"`
- `is_wayland() -> bool`
- `is_x11() -> bool`

Replaces 6+ duplicated `os.environ.get("XDG_SESSION_TYPE")` checks across the codebase.

## Controllers

### CaptureController (`capture/controller.py`)

Owns all capture workflows:

- `capture_fullscreen()`, `capture_region()`, `capture_ocr()`
- `capture_color_picker()`, `capture_ruler()`, `capture_qr_scan()`
- `generate_qr_from_clipboard()`, `scan_qr_from_clipboard()`
- `pin_region()`, `start_recording()`, `stop_recording()`
- `_save_and_notify()` — the shared save → clipboard → upload → notify pipeline

### UploadController (`upload/controller.py`)

Owns the upload lifecycle:

- Uploader factory (selects backend from settings)
- Background dispatch via TaskManager
- Upload success/error handling
- URL shortening pipeline

### ToolController (`tools/controller.py`)

Owns standalone tool dialog launching:

- Image Editor, Hash Checker, Directory Indexer, History Viewer

## Module Map

```
src/shotx/
├── app.py                  # Thin orchestrator (DI container)
├── main.py                 # CLI entry point
├── capture/
│   ├── controller.py       # CaptureController
│   ├── factory.py          # Backend auto-detection
│   ├── wayland.py          # Wayland capture backend
│   ├── x11.py              # X11 capture backend
│   ├── recorder.py         # Screen recording
│   └── region_detect.py    # AT-SPI2 + window detection
├── config/
│   └── settings.py         # SettingsManager + dataclasses
├── core/
│   ├── events.py           # EventBus singleton
│   ├── tasks.py            # TaskManager singleton
│   ├── platform.py         # Wayland/X11 detection
│   └── xdg.py              # File/folder opening
├── db/
│   └── history.py          # SQLite history manager
├── output/
│   ├── clipboard.py        # Clipboard operations
│   └── file_saver.py       # Image saving with patterns
├── tools/
│   ├── controller.py       # ToolController
│   ├── ocr.py              # Tesseract OCR
│   ├── qr.py               # QR scan/generate
│   └── indexer.py          # Directory indexer
├── ui/
│   ├── tray.py             # System tray icon + menu
│   ├── main_window.py      # Main Window (hub)
│   ├── overlay.py          # Region selection overlay
│   ├── editor.py           # Image editor window
│   ├── notification.py     # Desktop notifications
│   ├── history.py          # History viewer widget
│   └── ...                 # Other UI components
└── upload/
    ├── controller.py       # UploadController
    ├── worker.py           # Background upload QRunnable
    ├── image_hosts.py      # Imgur, ImgBB, tmpfiles
    ├── s3.py               # S3 uploader
    ├── ftp.py              # FTP/SFTP uploader
    ├── custom.py           # .sxcu custom uploader
    ├── shortener.py        # URL shortener
    └── base.py             # UploaderBackend interface
```

## Design Principles

1. **No circular dependencies** — EventBus has zero dependencies; controllers import only what they need
2. **Separation of concerns** — UI never contains business logic; controllers never touch UI widgets
3. **Lazy imports** — Heavy UI modules are imported inline for performance
4. **Dependency injection** — Controllers receive `SettingsManager` and `HistoryManager` via constructors
5. **Signal-based communication** — Components decouple via EventBus signals, not direct references
