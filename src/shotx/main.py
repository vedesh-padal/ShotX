"""ShotX entry point.

This module is the CLI entry point for ShotX. It handles argument parsing
and decides whether to launch the tray app or perform a one-shot capture.
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
        help="Capture a selected region and exit. (Coming soon)",
    )
    parser.add_argument(
        "--capture-window",
        action="store_true",
        help="Capture the active window and exit. (Coming soon)",
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

    if args.verbose:
        print(f"ShotX v{_get_version()}")
        print(f"Python {sys.version}")

    # One-shot capture modes
    if args.capture_fullscreen:
        # TODO: Implement in Commit 9 (app.py wiring)
        print("Fullscreen capture not yet implemented.")
        return 1

    if args.capture_region:
        print("Region capture will be available in a future update (Phase 2).")
        return 1

    if args.capture_window:
        print("Window capture will be available in a future update (Phase 2).")
        return 1

    # Default: launch tray app
    # TODO: Implement in Commit 9 (app.py wiring)
    print("ShotX tray app not yet implemented. Use --capture-fullscreen for now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
