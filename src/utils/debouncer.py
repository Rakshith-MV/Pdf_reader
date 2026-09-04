from PySide6.QtCore import QObject, QTimer, Slot
from typing import Callable

class Debouncer(QObject):
    """
    Debounces calls to a callback function using PySide6 QTimer.
    Ensures state updates (like current reading position) are not written
    to SQLite on every single pixel scroll, but rather 300ms after user stops scrolling.
    """

    def __init__(self, interval_ms: int, callback: Callable, parent: QObject = None):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.callback = callback
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timeout)
        self._pending_args = ()
        self._pending_kwargs = {}
        self._has_pending = False

    def trigger(self, *args, **kwargs):
        self._pending_args = args
        self._pending_kwargs = kwargs
        self._has_pending = True
        self.timer.start(self.interval_ms)

    @Slot()
    def _on_timeout(self):
        if self._has_pending:
            self._has_pending = False
            self.callback(*self._pending_args, **self._pending_kwargs)

    def flush(self):
        """Forces immediate execution of pending callback if timer is active."""
        if self.timer.isActive() or self._has_pending:
            self.timer.stop()
            self._has_pending = False
            self.callback(*self._pending_args, **self._pending_kwargs)
