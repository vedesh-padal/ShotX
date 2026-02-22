"""Settings management for ShotX.

All user preferences are stored in a single YAML file at
~/.config/shotx/settings.yaml (or $XDG_CONFIG_HOME/shotx/settings.yaml).

Settings are represented as dataclasses for type safety and easy
serialization. Missing keys are filled with defaults on load.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


def _default_output_dir() -> str:
    """Return default screenshot output directory."""
    pictures = os.environ.get("XDG_PICTURES_DIR")
    if pictures:
        return str(Path(pictures) / "ShotX")
    return str(Path.home() / "Pictures" / "ShotX")


def _default_config_dir() -> str:
    """Return default config directory following XDG Base Directory spec."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(Path(xdg_config) / "shotx")
    return str(Path.home() / ".config" / "shotx")


@dataclass
class CaptureSettings:
    """Settings related to screen capture behavior."""

    output_dir: str = ""  # Filled by post_init if empty
    filename_pattern: str = "ShotX_{date}_{time}"
    image_format: str = "png"  # png, jpg, webp
    jpeg_quality: int = 95
    copy_to_clipboard: bool = True
    save_to_file: bool = True
    show_notification: bool = True
    play_sound: bool = False
    auto_detect_regions: bool = True
    after_capture_action: str = "edit"  # "edit" or "save"
    last_annotation_color: str = "#ff0000"  # Persisted between sessions
    video_fps: int = 30
    capture_audio: bool = False

    def __post_init__(self) -> None:
        if not self.output_dir:
            self.output_dir = _default_output_dir()

        # Validate image format
        valid_formats = {"png", "jpg", "jpeg", "webp"}
        if self.image_format.lower() not in valid_formats:
            raise ValueError(
                f"Invalid image format '{self.image_format}'. "
                f"Must be one of: {', '.join(sorted(valid_formats))}"
            )
        self.image_format = self.image_format.lower()

        # Validate after_capture_action
        valid_actions = {"edit", "save"}
        if self.after_capture_action not in valid_actions:
            raise ValueError(
                f"Invalid after_capture_action '{self.after_capture_action}'. "
                f"Must be one of: {', '.join(valid_actions)}"
            )

        # Validate JPEG quality
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError(
                f"jpeg_quality must be between 1 and 100, got {self.jpeg_quality}"
            )


@dataclass
class HotkeySettings:
    """Settings for global keyboard shortcuts."""

    capture_fullscreen: str = "Print"
    capture_region: str = "<Ctrl>Print"
    capture_window: str = "<Alt>Print"


@dataclass
class AppSettings:
    """Top-level application settings container."""

    capture: CaptureSettings = field(default_factory=CaptureSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    first_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings to a plain dict (for YAML output)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Deserialize settings from a dict, filling missing keys with defaults.

        Unknown keys are silently ignored — this ensures forward compatibility
        when a user downgrades to an older version of ShotX.
        """
        capture_data = data.get("capture", {})
        hotkey_data = data.get("hotkeys", {})

        # Filter to only known fields to avoid TypeError on unexpected keys
        capture_fields = {f.name for f in CaptureSettings.__dataclass_fields__.values()}
        hotkey_fields = {f.name for f in HotkeySettings.__dataclass_fields__.values()}

        capture = CaptureSettings(
            **{k: v for k, v in capture_data.items() if k in capture_fields}
        )
        hotkeys = HotkeySettings(
            **{k: v for k, v in hotkey_data.items() if k in hotkey_fields}
        )

        return cls(
            capture=capture,
            hotkeys=hotkeys,
            first_run=data.get("first_run", True),
        )


class SettingsManager:
    """Handles loading and saving settings to/from YAML files.

    The settings file path is determined by XDG_CONFIG_HOME or defaults
    to ~/.config/shotx/settings.yaml.
    """

    FILENAME = "settings.yaml"

    def __init__(self, config_dir: str | None = None) -> None:
        self.config_dir = Path(config_dir) if config_dir else Path(_default_config_dir())
        self.settings_path = self.config_dir / self.FILENAME
        self._settings: AppSettings | None = None

    @property
    def settings(self) -> AppSettings:
        """Return current settings, loading from disk if not yet loaded."""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def load(self) -> AppSettings:
        """Load settings from YAML file.

        If the file doesn't exist, returns defaults and saves them.
        If the file has missing keys, defaults are used for those keys.
        """
        if not self.settings_path.exists():
            settings = AppSettings()
            self.save(settings)
            return settings

        try:
            with open(self.settings_path) as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            print(f"Warning: Could not read settings from {self.settings_path}: {e}")
            print("Using default settings.")
            return AppSettings()

        if not isinstance(data, dict):
            return AppSettings()

        settings = AppSettings.from_dict(data)
        self._settings = settings
        return settings

    def save(self, settings: AppSettings | None = None) -> None:
        """Save settings to YAML file.

        Creates the config directory if it doesn't exist.
        """
        if settings is None:
            settings = self.settings

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        data = settings.to_dict()

        with open(self.settings_path, "w") as f:
            f.write("# ShotX Configuration\n")
            f.write("# https://github.com/vedesh-padal/shotx\n\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        self._settings = settings

    def reset(self) -> AppSettings:
        """Reset settings to defaults and save."""
        settings = AppSettings()
        self.save(settings)
        return settings
