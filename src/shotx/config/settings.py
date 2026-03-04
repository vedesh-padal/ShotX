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
    show_notification: bool = True
    play_sound: bool = False
    auto_detect_regions: bool = True
    after_capture_action: str = "edit"  # "edit" or "save"
    last_annotation_color: str = "#ff0000"  # Persisted between sessions
    show_cursor: bool = False
    screenshot_delay: int = 0
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
    capture_region: str = "Ctrl+Print"
    capture_window: str = "Alt+Print"
    capture_ocr: str = ""
    capture_color_picker: str = ""
    capture_ruler: str = ""
    capture_qr_scan: str = ""
    pin_region: str = ""


@dataclass
class ImgurConfig:
    client_id: str = ""
    access_token: str = ""

@dataclass
class ImgBBConfig:
    api_key: str = ""

@dataclass
class S3Config:
    endpoint_url: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket_name: str = ""
    public_url_format: str = ""

@dataclass
class FtpConfig:
    host: str = ""
    port: int = 21
    username: str = ""
    password: str = ""
    remote_dir: str = "/"
    public_url_format: str = ""

@dataclass
class SftpConfig:
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    key_file: str = ""
    remote_dir: str = "/"
    public_url_format: str = ""

@dataclass
class UrlShortenerConfig:
    enabled: bool = False
    provider: str = "tinyurl"  # "tinyurl", "isgd", "vgd"

@dataclass
class UploadSettings:
    """Settings related to the upload engine."""
    enabled: bool = False
    default_uploader: str = "tmpfiles"
    copy_url_to_clipboard: bool = True
    
    imgur: ImgurConfig = field(default_factory=ImgurConfig)
    imgbb: ImgBBConfig = field(default_factory=ImgBBConfig)
    s3: S3Config = field(default_factory=S3Config)
    ftp: FtpConfig = field(default_factory=FtpConfig)
    sftp: SftpConfig = field(default_factory=SftpConfig)
    shortener: UrlShortenerConfig = field(default_factory=UrlShortenerConfig)


@dataclass
class WorkflowSettings:
    """Configurable pipeline of actions to execute sequentially after a capture."""
    save_to_file: bool = True
    copy_to_clipboard: bool = True
    upload_image: bool = False
    open_in_editor: bool = False


@dataclass
class AppSettings:
    """Top-level application settings container."""

    capture: CaptureSettings = field(default_factory=CaptureSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    upload: UploadSettings = field(default_factory=UploadSettings)
    workflow: WorkflowSettings = field(default_factory=WorkflowSettings)
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
        upload_data = data.get("upload", {})
        workflow_data = data.get("workflow", {})

        # Backward compatibility for old boolean-based capture/upload settings (v1)
        if "workflow" not in data:
            workflow_data["save_to_file"] = capture_data.get("save_to_file", True)
            workflow_data["copy_to_clipboard"] = capture_data.get("copy_to_clipboard", True)
            workflow_data["upload_image"] = upload_data.get("enabled", False)
            
        # Backward compatibility for old list-based workflow settings (v2)
        if "after_capture" in workflow_data and isinstance(workflow_data["after_capture"], list):
            old_list = workflow_data.pop("after_capture")
            workflow_data["save_to_file"] = "save_to_file" in old_list
            workflow_data["copy_to_clipboard"] = "copy_to_clipboard" in old_list
            workflow_data["upload_image"] = "upload_image" in old_list
            workflow_data["open_in_editor"] = "open_in_editor" in old_list

        # Filter to only known fields to avoid TypeError on unexpected keys
        capture_fields = {f.name for f in CaptureSettings.__dataclass_fields__.values()}
        hotkey_fields = {f.name for f in HotkeySettings.__dataclass_fields__.values()}
        workflow_fields = {f.name for f in WorkflowSettings.__dataclass_fields__.values()}
        
        # Upload fields need special dictionary handling for sub-configs
        upload_fields = {f.name for f in UploadSettings.__dataclass_fields__.values()}
        imgur_fields = {f.name for f in ImgurConfig.__dataclass_fields__.values()}
        imgbb_fields = {f.name for f in ImgBBConfig.__dataclass_fields__.values()}
        s3_fields = {f.name for f in S3Config.__dataclass_fields__.values()}
        ftp_fields = {f.name for f in FtpConfig.__dataclass_fields__.values()}
        sftp_fields = {f.name for f in SftpConfig.__dataclass_fields__.values()}
        shortener_fields = {f.name for f in UrlShortenerConfig.__dataclass_fields__.values()}

        capture = CaptureSettings(
            **{k: v for k, v in capture_data.items() if k in capture_fields}
        )
        hotkeys = HotkeySettings(
            **{k: v for k, v in hotkey_data.items() if k in hotkey_fields}
        )
        workflow = WorkflowSettings(
            **{k: v for k, v in workflow_data.items() if k in workflow_fields}
        )
        
        imgur_data = upload_data.get("imgur", {})
        imgbb_data = upload_data.get("imgbb", {})
        s3_data = upload_data.get("s3", {})
        ftp_data = upload_data.get("ftp", {})
        sftp_data = upload_data.get("sftp", {})
        shortener_data = upload_data.get("shortener", {})
        
        imgur_config = ImgurConfig(**{k: v for k, v in imgur_data.items() if k in imgur_fields})
        imgbb_config = ImgBBConfig(**{k: v for k, v in imgbb_data.items() if k in imgbb_fields})
        s3_config = S3Config(**{k: v for k, v in s3_data.items() if k in s3_fields})
        ftp_config = FtpConfig(**{k: v for k, v in ftp_data.items() if k in ftp_fields})
        sftp_config = SftpConfig(**{k: v for k, v in sftp_data.items() if k in sftp_fields})
        shortener_config = UrlShortenerConfig(**{k: v for k, v in shortener_data.items() if k in shortener_fields})
        
        upload_kwargs = {k: v for k, v in upload_data.items() if k in upload_fields and isinstance(v, (str, bool, int))}
        upload = UploadSettings(
            imgur=imgur_config,
            imgbb=imgbb_config,
            s3=s3_config,
            ftp=ftp_config,
            sftp=sftp_config,
            shortener=shortener_config,
            **upload_kwargs
        )

        return cls(
            capture=capture,
            hotkeys=hotkeys,
            upload=upload,
            workflow=workflow,
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
            f.write("# https://github.com/vedesh-padal/ShotX\n\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        self._settings = settings

    def reset(self) -> AppSettings:
        """Reset settings to defaults and save."""
        settings = AppSettings()
        self.save(settings)
        return settings
