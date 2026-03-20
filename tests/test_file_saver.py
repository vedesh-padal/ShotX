"""Tests for filename processing and image saving."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from shotx.output.file_saver import expand_filename_pattern, save_image


class TestFilenamePattern:
    """Tests for filename pattern expansion."""

    def test_date_variable(self) -> None:
        """Date variable should produce YYYY-MM-DD format."""
        result = expand_filename_pattern("shot_{date}")
        # Should match YYYY-MM-DD pattern
        parts = result.replace("shot_", "").split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert len(parts[1]) == 2  # month
        assert len(parts[2]) == 2  # day

    def test_time_variable(self) -> None:
        """Time variable should produce HH-MM-SS format."""
        result = expand_filename_pattern("{time}")
        parts = result.split("-")
        assert len(parts) == 3

    def test_type_variable(self) -> None:
        """Type variable should be replaced with capture type."""
        result = expand_filename_pattern("shot_{type}", capture_type="region")
        assert result == "shot_region"

    def test_counter_variable(self) -> None:
        """Counter should be zero-padded to 4 digits."""
        result = expand_filename_pattern("shot_{counter}", counter=42)
        assert result == "shot_0042"

    def test_multiple_variables(self) -> None:
        """Multiple variables should all be expanded."""
        result = expand_filename_pattern("ShotX_{date}_{type}")
        assert "ShotX_" in result
        assert "fullscreen" in result  # default capture_type
        assert "{" not in result  # no unexpanded vars

    def test_no_variables(self) -> None:
        """Pattern without variables should pass through unchanged."""
        result = expand_filename_pattern("screenshot")
        assert result == "screenshot"


class TestSaveImage:
    """Tests for image saving.

    Note: These tests create a minimal QImage. They require a QGuiApplication
    which is created by the test fixtures.
    """

    @pytest.fixture(autouse=True)
    def _ensure_qapp(self, qapp) -> None:
        """Ensure QApplication is initialized via pytest-qt fixture."""
        pass

    def _make_test_image(self, width: int = 100, height: int = 80) -> QImage:
        """Create a simple test image."""
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(QColor(100, 150, 200))
        return image

    def test_save_png(self, tmp_path: Path) -> None:
        """Should save a PNG file."""
        image = self._make_test_image()
        result = save_image(image, str(tmp_path), image_format="png")

        assert result is not None
        assert result.exists()
        assert result.suffix == ".png"
        assert result.stat().st_size > 0

    def test_save_jpg(self, tmp_path: Path) -> None:
        """Should save a JPG file."""
        image = self._make_test_image()
        result = save_image(image, str(tmp_path), image_format="jpg")

        assert result is not None
        assert result.exists()
        assert result.suffix == ".jpg"

    def test_save_webp(self, tmp_path: Path) -> None:
        """Should save a WebP file."""
        image = self._make_test_image()
        result = save_image(image, str(tmp_path), image_format="webp")

        assert result is not None
        assert result.exists()
        assert result.suffix == ".webp"

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        """Should create the output directory if it doesn't exist."""
        output_dir = tmp_path / "deep" / "nested" / "dir"
        image = self._make_test_image()
        result = save_image(image, str(output_dir))

        assert result is not None
        assert output_dir.exists()
        assert result.exists()

    def test_collision_avoidance(self, tmp_path: Path) -> None:
        """Should append counter if file already exists."""
        image = self._make_test_image()

        path1 = save_image(image, str(tmp_path), filename_pattern="test", image_format="png")
        path2 = save_image(image, str(tmp_path), filename_pattern="test", image_format="png")

        assert path1 is not None
        assert path2 is not None
        assert path1 != path2
        assert path1.name == "test.png"
        assert path2.name == "test_1.png"

    def test_unsupported_format(self, tmp_path: Path) -> None:
        """Unsupported format should return None."""
        image = self._make_test_image()
        result = save_image(image, str(tmp_path), image_format="bmp")
        assert result is None

    def test_null_image(self, tmp_path: Path) -> None:
        """Null image should return None."""
        from PySide6.QtGui import QImage

        null_image = QImage()
        result = save_image(null_image, str(tmp_path))
        assert result is None
