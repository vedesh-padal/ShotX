from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject

from shotx.core.events import EventBus
from shotx.core.platform import is_wayland, is_x11, session_type
from shotx.core.tasks import TaskManager


class TestEventBus:

    def test_singleton(self, qapp):
        """EventBus should be a module-level singleton."""
        from shotx.core.events import event_bus as bus1
        from shotx.core.events import event_bus as bus2
        assert bus1 is bus2
        assert isinstance(bus1, QObject)

    def test_signals_exist(self, qapp):
        """EventBus should define the core application signals."""
        bus = EventBus()

        assert hasattr(bus, "capture_requested")
        assert hasattr(bus, "tool_requested")
        assert hasattr(bus, "upload_requested")
        assert hasattr(bus, "upload_completed")
        assert hasattr(bus, "upload_failed")
        assert hasattr(bus, "notify_info_requested")
        assert hasattr(bus, "notify_error_requested")


class TestTaskManager:

    def test_singleton(self, qapp):
        """TaskManager should be a module-level singleton."""
        from shotx.core.tasks import task_manager as tm1
        from shotx.core.tasks import task_manager as tm2
        assert tm1 is tm2

    def test_active_runnables_tracking(self, qapp):
        """TaskManager should track active runnables to prevent premature GC."""
        tm = TaskManager()

        # Mock worker
        worker = MagicMock()
        worker.autoDelete = MagicMock(return_value=True)

        # Submit worker
        with patch.object(tm._pool, "start") as mock_start:
            tm.submit(worker, tag="test_worker")

            # Ensure it was passed to QThreadPool
            mock_start.assert_called_once_with(worker)

            # Ensure it is tracked
            assert "test_worker" in tm._active

            # Simulate worker completing
            tm.release("test_worker")
            assert len(tm._active) == 0


class TestPlatform:

    @patch("shotx.core.platform.os.environ.get")
    def test_session_type_wayland(self, mock_env):
        """Should detect Wayland via XDG_SESSION_TYPE or WAYLAND_DISPLAY."""
        mock_env.side_effect = lambda k, d="": "wayland" if k == "XDG_SESSION_TYPE" else d

        # Clear lru_cache for testing
        session_type.cache_clear()

        assert session_type() == "wayland"
        assert is_wayland() is True
        assert is_x11() is False

    @patch("shotx.core.platform.os.environ.get")
    def test_session_type_x11(self, mock_env):
        """Should detect X11 via XDG_SESSION_TYPE or DISPLAY."""
        mock_env.side_effect = lambda k, d="": "x11" if k == "XDG_SESSION_TYPE" else d

        # Clear lru_cache for testing
        session_type.cache_clear()

        assert session_type() == "x11"
        assert is_wayland() is False
        assert is_x11() is True

    @patch("shotx.core.platform.os.environ.get")
    def test_session_type_unknown(self, mock_env):
        """Should fallback to unknown if no standard env vars are present."""
        mock_env.return_value = ""

        # Clear lru_cache for testing
        session_type.cache_clear()

        assert session_type() == "unknown"
        assert is_wayland() is False
        assert is_x11() is False
