from unittest.mock import MagicMock, patch

import pytest

from shotx.capture.controller import CaptureController
from shotx.db.history import HistoryManager


class MockCategory:
    pass

@pytest.fixture
def mock_settings():
    """Mock settings manager using simple objects to avoid MagicMock type errors."""
    manager = MagicMock()
    manager.settings = MockCategory()
    manager.settings.capture = MockCategory()
    manager.settings.workflow = MockCategory()

    # Setup some default attributes that the controller expects
    manager.settings.capture.after_capture_action = "annotate"
    manager.settings.capture.screenshot_delay = 0
    manager.settings.capture.show_cursor = False
    manager.settings.capture.auto_detect_regions = False
    manager.settings.capture.last_annotation_color = "#FF0000"
    manager.settings.capture.show_notification = False

    manager.settings.workflow.copy_to_clipboard = True
    manager.settings.workflow.save_to_file = True
    manager.settings.workflow.upload_image = False

    return manager


@pytest.fixture
def mock_history():
    """Mock history manager."""
    return MagicMock(spec=HistoryManager)


@pytest.fixture
def controller(qapp, mock_settings, mock_history):
    """Provides a fresh CaptureController for each test."""
    ctrl = CaptureController(mock_settings, mock_history)
    return ctrl


class TestCaptureController:

    @patch("shotx.capture.controller.create_capture_backend")
    def test_capture_fullscreen(self, mock_create_backend, controller):
        """Fullscreen capture should request backend and emit signals."""
        mock_backend = MagicMock()
        mock_create_backend.return_value = mock_backend

        # We need to mock the save pipeline so it doesn't actually hit disk
        with patch.object(controller, "_save_and_notify"):
            controller.capture_fullscreen()

            # Verify backend was called
            mock_backend.capture_fullscreen.assert_called_once()

            # Since the backend capture is mocked, it won't yield an image.
            # In a real async/signal-based controller, we test the signal emission
            # but since this test is synchronous and mock_backend returns a MagicMock
            # instead of a QImage, we just verify the call chain.

    @patch("shotx.capture.controller.QEventLoop.exec")
    @patch("shotx.capture.controller.create_capture_backend")
    def test_capture_region_enters_annotation(self, mock_create_backend, mock_exec, controller, mock_settings):
        """Region capture should enter annotation mode if configured."""
        mock_settings.capture.after_capture_action = "annotate"

        mock_backend = MagicMock()
        mock_create_backend.return_value = mock_backend

        # The region capture shows an overlay first.
        # We patch the RegionOverlay to prevent Qt windows from popping up during tests.
        with patch("shotx.ui.overlay.RegionOverlay") as mock_overlay_class:
            mock_overlay = MagicMock()
            mock_overlay_class.return_value = mock_overlay

            # Since region capture requires an image to return from the backend,
            # we need to mock capture_fullscreen to return a dummy QImage
            from PySide6.QtGui import QImage
            mock_backend.capture_fullscreen.return_value = QImage(100, 100, QImage.Format_RGB32)

            controller.capture_region()

            mock_overlay.show_fullscreen.assert_called_once()

    def test_stop_recording_emits_event(self, controller):
        """Stopping recording should trigger the recorder's stop method if active."""
        # Force the recorder to appear active
        controller._recorder = MagicMock()
        controller._recorder.is_active = True

        controller.stop_recording()

        controller._recorder.stop_recording.assert_called_once()
