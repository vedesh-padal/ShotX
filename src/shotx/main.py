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
        "--shorten-url",
        type=str,
        nargs="?",
        const="USE_CLIPBOARD",
        default=None,
        help="Shorten a URL. If no URL is provided, reads from the clipboard. Prints to stdout.",
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
        "--history",
        action="store_true",
        help="Open the History Viewer to browse past captures.",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Launch the system tray app (default behavior).",
    )
    parser.add_argument(
        "--setup-desktop",
        action="store_true",
        help="Install the ShotX .desktop file to the application menu.",
    )
    parser.add_argument(
        "--remove-desktop",
        action="store_true",
        help="Remove the ShotX .desktop file from the application menu.",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Install the ShotX autostart entry so it launches on login.",
    )
    parser.add_argument(
        "--remove-autostart",
        action="store_true",
        help="Remove the ShotX autostart entry.",
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

    if args.install_autostart:
        from shotx.core.desktop import install_autostart
        if install_autostart():
            print("Successfully installed XDG autostart entry.")
            return 0
        else:
            print("Failed to install XDG autostart entry.", file=sys.stderr)
            return 1

    if args.remove_autostart:
        from shotx.core.desktop import remove_autostart
        if remove_autostart():
            print("Successfully removed XDG autostart entry.")
            return 0
        else:
            print("Failed to remove XDG autostart entry.", file=sys.stderr)
            return 1
            
    if args.setup_desktop:
        from shotx.core.desktop import install_desktop_menu
        if install_desktop_menu():
            print("Successfully installed ShotX to application menu.")
            return 0
        else:
            print("Failed to install ShotX to application menu.", file=sys.stderr)
            return 1

    if args.remove_desktop:
        from shotx.core.desktop import remove_desktop_menu
        if remove_desktop_menu():
            print("Successfully removed ShotX from application menu.")
            return 0
        else:
            print("Failed to remove ShotX from application menu.", file=sys.stderr)
            return 1

    # Determine if this is a one-shot command or the tray app
    is_oneshot = (
        args.capture_fullscreen or args.capture_region or args.capture_window or
        args.ocr or args.color_picker or args.ruler or args.qr_scan or
        args.qr_generate or args.qr_scan_clipboard or args.pin_region or
        args.shorten_url is not None or args.hash or args.index_dir is not None or
        args.edit is not None or args.history
    )

    if is_oneshot:
        import os
        # Suppress benign Qt Wayland DBus app registration warnings that clutter stdout
        os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"

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
    qt_app.setDesktopFileName("shotx")
    qt_app.setApplicationVersion(_get_version())
    
    # Load and set application icon
    try:
        from PySide6.QtGui import QIcon
        import importlib.resources as pkg_resources
        icon_path = pkg_resources.files("shotx.assets").joinpath("shotx.png")
        if icon_path.exists():
            qt_app.setWindowIcon(QIcon(str(icon_path)))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to load application icon: %s", e)
        
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
    elif args.shorten_url is not None:
        url_to_shorten = None if args.shorten_url == "USE_CLIPBOARD" else args.shorten_url
        return app.run_oneshot("shorten_url", url=url_to_shorten)
    elif args.hash:
        return app.run_oneshot("hash")
    elif args.index_dir is not None:
        return app.run_oneshot("index_dir", start_path=args.index_dir)
    elif args.edit is not None:
        return app.run_oneshot("edit", image_path=args.edit)
    elif args.history:
        return app.run_oneshot("history")

    # Default: launch tray app
    return app.run_tray()


if __name__ == "__main__":
    sys.exit(main())
