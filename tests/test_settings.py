"""Tests for ShotX settings management."""

from __future__ import annotations

import pytest
from pathlib import Path

from shotx.config.settings import AppSettings, CaptureSettings, HotkeySettings, SettingsManager


class TestCaptureSettings:
    """Tests for CaptureSettings dataclass."""

    def test_defaults(self) -> None:
        """Default settings should have sensible values."""
        s = CaptureSettings()
        assert s.image_format == "png"
        assert s.jpeg_quality == 95
        assert s.copy_to_clipboard is True
        assert s.save_to_file is True
        assert s.show_notification is True
        assert s.play_sound is False
        assert "ShotX" in s.output_dir

    def test_valid_formats(self) -> None:
        """All supported image formats should be accepted."""
        for fmt in ("png", "jpg", "jpeg", "webp", "PNG", "JPG"):
            s = CaptureSettings(image_format=fmt)
            assert s.image_format == fmt.lower()

    def test_invalid_format_raises(self) -> None:
        """Invalid image format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid image format"):
            CaptureSettings(image_format="bmp")

    def test_jpeg_quality_bounds(self) -> None:
        """JPEG quality must be between 1 and 100."""
        CaptureSettings(jpeg_quality=1)   # Should not raise
        CaptureSettings(jpeg_quality=100) # Should not raise

        with pytest.raises(ValueError, match="jpeg_quality"):
            CaptureSettings(jpeg_quality=0)

        with pytest.raises(ValueError, match="jpeg_quality"):
            CaptureSettings(jpeg_quality=101)


class TestAppSettings:
    """Tests for AppSettings serialization and deserialization."""

    def test_round_trip(self) -> None:
        """Settings should survive a to_dict -> from_dict cycle."""
        original = AppSettings()
        data = original.to_dict()
        restored = AppSettings.from_dict(data)

        assert restored.capture.image_format == original.capture.image_format
        assert restored.capture.jpeg_quality == original.capture.jpeg_quality
        assert restored.capture.copy_to_clipboard == original.capture.copy_to_clipboard
        assert restored.hotkeys.capture_fullscreen == original.hotkeys.capture_fullscreen
        assert restored.first_run == original.first_run

    def test_missing_keys_use_defaults(self) -> None:
        """Missing keys in the dict should be filled with defaults."""
        data = {"capture": {"image_format": "jpg"}}
        settings = AppSettings.from_dict(data)

        assert settings.capture.image_format == "jpg"
        # Missing keys should have default values
        assert settings.capture.jpeg_quality == 95
        assert settings.capture.copy_to_clipboard is True
        assert settings.hotkeys.capture_fullscreen == "Print"
        assert settings.first_run is True

    def test_unknown_keys_ignored(self) -> None:
        """Unknown keys in the dict should be silently ignored."""
        data = {
            "capture": {"image_format": "png", "unknown_key": "value"},
            "hotkeys": {"capture_fullscreen": "F12", "future_setting": True},
            "some_new_section": {"key": "value"},
        }
        settings = AppSettings.from_dict(data)

        assert settings.capture.image_format == "png"
        assert settings.hotkeys.capture_fullscreen == "F12"

    def test_empty_dict(self) -> None:
        """Empty dict should produce all-defaults settings."""
        settings = AppSettings.from_dict({})
        defaults = AppSettings()

        assert settings.capture.image_format == defaults.capture.image_format
        assert settings.hotkeys.capture_fullscreen == defaults.hotkeys.capture_fullscreen


class TestSettingsManager:
    """Tests for YAML file load/save operations."""

    def test_creates_default_on_first_load(self, tmp_path: Path) -> None:
        """First load should create config file with defaults."""
        manager = SettingsManager(config_dir=str(tmp_path / "shotx"))
        settings = manager.load()

        assert settings.first_run is True
        assert manager.settings_path.exists()
        assert "ShotX Configuration" in manager.settings_path.read_text()

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Settings saved to YAML should load back correctly."""
        config_dir = str(tmp_path / "shotx")
        manager = SettingsManager(config_dir=config_dir)

        # Customize and save
        settings = AppSettings(
            capture=CaptureSettings(image_format="jpg", jpeg_quality=80),
            hotkeys=HotkeySettings(capture_fullscreen="F12"),
            first_run=False,
        )
        manager.save(settings)

        # Load in a new manager instance
        manager2 = SettingsManager(config_dir=config_dir)
        loaded = manager2.load()

        assert loaded.capture.image_format == "jpg"
        assert loaded.capture.jpeg_quality == 80
        assert loaded.hotkeys.capture_fullscreen == "F12"
        assert loaded.first_run is False

    def test_corrupted_file_returns_defaults(self, tmp_path: Path) -> None:
        """Corrupted YAML should fall back to defaults without crashing."""
        config_dir = tmp_path / "shotx"
        config_dir.mkdir(parents=True)

        settings_file = config_dir / "settings.yaml"
        settings_file.write_text("{{{{invalid yaml!!!!}")

        manager = SettingsManager(config_dir=str(config_dir))
        settings = manager.load()

        # Should return defaults, not crash
        assert settings.capture.image_format == "png"

    def test_reset(self, tmp_path: Path) -> None:
        """Reset should overwrite with defaults."""
        config_dir = str(tmp_path / "shotx")
        manager = SettingsManager(config_dir=config_dir)

        # Customize
        custom = AppSettings(
            capture=CaptureSettings(image_format="webp"),
            first_run=False,
        )
        manager.save(custom)

        # Reset
        settings = manager.reset()
        assert settings.capture.image_format == "png"
        assert settings.first_run is True

        # Verify persisted
        loaded = SettingsManager(config_dir=config_dir).load()
        assert loaded.capture.image_format == "png"
