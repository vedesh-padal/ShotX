"""ShotX entry point.

This module is the CLI entry point for ShotX. It handles argument parsing
and decides whether to launch the tray app or perform a one-shot capture.

Usage:
    shotx                       # Launch as system tray app
    shotx --capture-fullscreen  # One-shot fullscreen capture
    shotx --version             # Print version and exit
    shotx --help                # Show help
"""

from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="shotx",
        description="ShotX — Screenshot and screen capture tool for Linux.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    parser.add_argument(
        "--capture-fullscreen",
        action="store_true",
        help="Capture fullscreen and exit.",
    )
    parser.add_argument(
        "--capture-region",
        action="store_true",
        help="Capture a selected region and exit.",
    )
    parser.add_argument(
        "--capture-window",
        action="store_true",
        help="Capture the active window and exit.",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Select a region and extract Text (OCR) to clipboard.",
    )
    parser.add_argument(
        "--color-picker",
        action="store_true",
        help="Open magnifier to extract a pixel's exact color code to clipboard.",
    )
    parser.add_argument(
        "--ruler",
        action="store_true",
        help="Open screen ruler to measure pixel distances and boundaries.",
    )
    parser.add_argument(
        "--qr-scan",
        action="store_true",
        help="Select a region and scan for a QR code.",
    )
    parser.add_argument(
        "--qr-generate",
        action="store_true",
        help="Generate a QR code from the current clipboard text.",
    )
    parser.add_argument(
        "--qr-scan-clipboard",
        action="store_true",
        help="Scan the current clipboard image for a QR code.",
    )
    parser.add_argument(
        "--pin-region", 
        action="store_true", 
        help="Capture a region and pin it as a floating window"
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help="Open the hash checker tool",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        nargs="?",
        const="",
        help="Open the Directory Indexer (optionally provide a starting path).",
    )
    parser.add_argument(
        "--edit",
        type=str,
        nargs="?",
        const="",
        help="Open the Image Editor (optionally provide a starting image path).",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Launch the system tray app (default behavior).",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default=None,
        help="Override the config directory (default: ~/.config/shotx).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output (show backend selection, capture details).",
    )
    return parser.parse_args(argv)


def _get_version() -> str:
    """Read version from package metadata."""
    from shotx import __version__

    return __version__


def main(argv: list[str] | None = None) -> int:
    """Main entry point for ShotX.

    When called with capture flags (--capture-fullscreen, etc.), performs
    a one-shot capture and exits. Otherwise, launches the system tray app.
    """
    args = parse_args(argv)

    # Ensure Ctrl+C from terminal instantly kills the process, even if 
    # the PySide6 C++ event loop (exec_) is running and blocking Python.
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # QApplication must be created before any Qt operations.
    # We create it early because both tray and one-shot modes need it
    # (one-shot needs it for QImage, clipboard, and screen access).
    from PySide6.QtWidgets import QApplication

    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("ShotX")
    qt_app.setApplicationVersion(_get_version())
    qt_app.setStyleSheet("QToolTip { color: white; background-color: #2b2b2b; border: 1px solid #555; }")

    # Create the app controller
    from shotx.app import ShotXApp

    app = ShotXApp(config_dir=args.config_dir, verbose=args.verbose)

    # One-shot capture modes
    if args.capture_fullscreen:
        return app.run_oneshot("fullscreen")

    if args.capture_region:
        return app.run_oneshot("region")

    if args.capture_window:
        return app.run_oneshot("window")

    if args.ocr:
        return app.run_oneshot("ocr")

    if args.color_picker:
        return app.run_oneshot("color_picker")

    if args.ruler:
        return app.run_oneshot("ruler")

    if args.qr_scan:
        return app.run_oneshot("qr_scan")

    if args.qr_generate:
        return app.run_oneshot("qr_generate")

    if args.qr_scan_clipboard:
        return app.run_oneshot("qr_scan_clipboard")

    elif args.pin_region:
        return app.run_oneshot("pin_region")
    elif args.hash:
        return app.run_oneshot("hash")
    elif args.index_dir is not None:
        return app.run_oneshot("index_dir", start_path=args.index_dir)
    elif args.edit is not None:
        return app.run_oneshot("edit", image_path=args.edit)

    # Default: launch tray app
    return app.run_tray()


if __name__ == "__main__":
    sys.exit(main())
