"""Managed thread pool for background workers.

Wraps ``QThreadPool`` and keeps strong references to active ``QRunnable``
workers so Python's garbage collector cannot destroy their signal objects
before the worker thread completes.  This fixes the race condition where
Qt signals (success/error) were posted to the main event loop but the
Python closure that owned them was already collected.

Usage::

    from shotx.core.tasks import task_manager

    worker = SomeQRunnable(...)
    task_manager.submit(worker, tag="upload_imgur")
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

logger = logging.getLogger(__name__)


class _TaskSignals(QObject):
    """Internal signals emitted by the TaskManager itself."""

    # Emitted when a tracked worker finishes (regardless of success/failure).
    # Payload: tag str
    worker_finished = Signal(str)


class TaskManager(QObject):
    """Lifecycle-safe wrapper around QThreadPool.

    Attributes:
        signals: Emits ``worker_finished(tag)`` when a tracked worker completes.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._active: dict[str, QRunnable] = {}
        self.signals = _TaskSignals()

    @property
    def active_count(self) -> int:
        """Number of workers currently tracked."""
        return len(self._active)

    def submit(self, worker: QRunnable, tag: str) -> None:
        """Submit a worker to the thread pool with lifecycle tracking.

        Args:
            worker: A ``QRunnable`` (typically with a ``signals`` attribute).
            tag: A human-readable identifier for logging and tracking.
        """
        # Hold a strong reference so Python won't GC the worker or its signals
        # while the C++ thread pool is still executing it.
        self._active[tag] = worker

        # If the worker exposes a ``signals`` object with ``finished``, wire
        # automatic cleanup.  Otherwise the caller must call ``release(tag)``.
        signals_obj = getattr(worker, "signals", None)
        if signals_obj is not None:
            # Many workers expose ``success`` and ``error`` but not ``finished``.
            # We connect to whichever is available; worst case the caller
            # releases manually.
            for sig_name in ("finished", "success", "error"):
                sig = getattr(signals_obj, sig_name, None)
                if sig is not None:
                    # Use a closure default to capture tag by value.
                    sig.connect(lambda *_args, t=tag: self._on_worker_done(t))
                    break

        logger.debug("TaskManager: submitted worker '%s'", tag)
        self._pool.start(worker)

    def release(self, tag: str) -> None:
        """Manually release a tracked worker reference."""
        if tag in self._active:
            del self._active[tag]
            logger.debug("TaskManager: released worker '%s'", tag)

    def wait_for_all(self, timeout_ms: int = 30_000) -> bool:
        """Block until all active workers finish (or timeout).

        Returns ``True`` if all workers finished within the timeout.
        """
        return self._pool.waitForDone(timeout_ms)

    # ------------------------------------------------------------------

    def _on_worker_done(self, tag: str) -> None:
        def cleanup() -> None:
            self.release(tag)
            self.signals.worker_finished.emit(tag)

        # Defer the cleanup to the next event loop tick so we don't garbage
        # collect the QRunnable while its signals are still actively emitting.
        QTimer.singleShot(0, cleanup)


# Module-level singleton.
task_manager = TaskManager()
