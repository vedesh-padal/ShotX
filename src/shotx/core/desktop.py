"""XDG Autostart management for ShotX.

This module handles copying an autostart .desktop file to the user's
~/.config/autostart directory, enabling "Start on Login" functionality
across all freedesktop.org compliant desktop environments (GNOME, KDE,
XFCE, Cinnamon, Sway, Hyprland, etc.).
"""

import importlib.resources as pkg_resources
import logging
import os
import shutil
import stat
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# XDG Paths
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

AUTOSTART_DIR = XDG_CONFIG_HOME / "autostart"
APP_DIR = XDG_DATA_HOME / "applications"
ICON_DIR = XDG_DATA_HOME / "icons" / "hicolor" / "512x512" / "apps"

DESKTOP_ENTRY_NAME = "shotx.desktop"


def get_executable_command(tray: bool = True) -> str:
    """Determine the command needed to launch ShotX."""
    executable = Path(sys.argv[0])
    cmd = ""
    if executable.name == "shotx" and executable.exists():
        cmd = str(executable)
    elif "shotx.main" in sys.argv[0] or executable.name == "main.py":
        cmd = f"{sys.executable} -m shotx.main"
    else:
        cmd = f"{sys.executable} -m shotx.main"

    if tray:
        return f"{cmd} --tray"
    return cmd


def _get_icon_path() -> str:
    try:
        return str(pkg_resources.files("shotx.assets").joinpath("shotx.png"))
    except Exception:
        return "camera-photo"


def _install_icon() -> None:
    target = ICON_DIR / "shotx.png"
    try:
        source = pkg_resources.files("shotx.assets").joinpath("shotx.png")
        if source.is_file():
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(target))
            logger.info("Installed system icon to %s", target)
    except Exception as e:
        logger.warning("Failed to install system icon to %s: %s", target, e)

def _remove_icon() -> None:
    target = ICON_DIR / "shotx.png"
    try:
        if target.exists():
            target.unlink()
            logger.info("Removed system icon: %s", target)
    except Exception as e:
        logger.warning("Failed to remove system icon %s: %s", target, e)


def _generate_desktop_content(is_autostart: bool = False) -> str:
    """Generate the contents of the .desktop file."""
    cmd_tray = get_executable_command(tray=True)
    cmd_base = get_executable_command(tray=False)
    icon_path = _get_icon_path()

    content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=ShotX
GenericName=Screenshot Tool
Comment=Screenshot and screen capture tool
Exec={cmd_tray}
Terminal=false
Categories=Utility;Graphics;
Keywords=screenshot;capture;sharex;
Icon={icon_path}
StartupNotify=true
"""
    if is_autostart:
        content += "NoDisplay=false\n"
        content += "X-GNOME-Autostart-enabled=true\n"
    else:
        # Add quick actions for the application menu / taskbar
        content += f"""Actions=Region;Fullscreen;Window;

[Desktop Action Region]
Name=Capture Region
Exec={cmd_base} --capture-region

[Desktop Action Fullscreen]
Name=Capture Fullscreen
Exec={cmd_base} --capture-fullscreen

[Desktop Action Window]
Name=Capture Window
Exec={cmd_base} --capture-window
"""
    return content


def _write_desktop_file(directory: Path, is_autostart: bool) -> bool:
    target_file = directory / DESKTOP_ENTRY_NAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w") as f:
            f.write(_generate_desktop_content(is_autostart))
        target_file.chmod(target_file.stat().st_mode | stat.S_IEXEC)
        logger.info("Created desktop entry at %s", target_file)
        return True
    except Exception as e:
        logger.error("Failed to create desktop entry at %s: %s", target_file, e)
        return False


def _remove_desktop_file(directory: Path) -> bool:
    target_file = directory / DESKTOP_ENTRY_NAME
    try:
        if target_file.exists():
            target_file.unlink()
            logger.info("Removed desktop entry: %s", target_file)
        return True
    except Exception as e:
        logger.error("Failed to remove desktop entry %s: %s", target_file, e)
        return False


# --- Autostart API ---

def is_autostart_enabled() -> bool:
    return (AUTOSTART_DIR / DESKTOP_ENTRY_NAME).exists()

def install_autostart() -> bool:
    return _write_desktop_file(AUTOSTART_DIR, is_autostart=True)

def remove_autostart() -> bool:
    return _remove_desktop_file(AUTOSTART_DIR)


# --- App Menu / Taskbar API ---

def install_desktop_menu() -> bool:
    """Install to ~/.local/share/applications for taskbar integration."""
    _install_icon()
    return _write_desktop_file(APP_DIR, is_autostart=False)

def remove_desktop_menu() -> bool:
    _remove_icon()
    return _remove_desktop_file(APP_DIR)
