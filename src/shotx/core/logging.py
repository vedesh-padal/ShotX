"""ShotX logging configuration.

Provides a unified way to configure logging across the application,
including colorized output for terminals.
"""

from __future__ import annotations

import logging
import sys


class ColoredFormatter(logging.Formatter):
    """Custom logging formatter that adds ANSI colors based on log level."""

    # ANSI escape sequences
    # https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[41m", # Red background
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors if it's a TTY."""
        level_color = self.COLORS.get(record.levelno, "")
        
        # We want to color parts of the message, not necessarily the whole line
        # to keep it readable.
        
        # Original format: "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        
        # Apply dim to timestamp and name
        timestamp = f"{self.DIM}{self.formatTime(record, self.datefmt)}{self.RESET}"
        # Pad logger name to 25 chars for consistent alignment
        name = f"{self.DIM}[{record.name:25}]{self.RESET}"
        
        # Apply color and bold to level, left-aligned in 8 chars
        level = f"{self.BOLD}{level_color}{record.levelname:<8}{self.RESET}"
        
        # Leave message as is, or maybe bold it for ERROR/CRITICAL
        message = record.getMessage()
        if record.levelno >= logging.ERROR:
            message = f"{self.BOLD}{message}{self.RESET}"

        return f"{timestamp} {name} {level}: {message}"


def setup_logging(verbose: bool = False) -> None:
    """Configure the root logger.

    Args:
        verbose: If True, set level to DEBUG and show more details.
    """
    level = logging.DEBUG if verbose else logging.WARNING

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Prevent duplicate handlers if called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Use colored formatter if outputting to a terminal
    if sys.stdout.isatty():
        # Pass None for fmt/datefmt as ColoredFormatter.format handles it
        formatter = ColoredFormatter(datefmt="%H:%M:%S")
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(name)-25s] %(levelname)-8s: %(message)s",
            datefmt="%H:%M:%S"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Silence noisy third-party libraries unless we're in deep debug
    if verbose:
        logging.getLogger("httpcore").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.INFO)
        # PySide6 can be quite chatty sometimes, we might want to tune it too
        # logging.getLogger("PySide6").setLevel(logging.INFO)
