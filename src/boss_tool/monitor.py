from __future__ import annotations

import threading
import time
from typing import Callable


class MonitorController:
    def __init__(self, scan_callback: Callable[[], None]) -> None:
        self.scan_callback = scan_callback
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, interval_seconds: int) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(interval_seconds,),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self, interval_seconds: int) -> None:
        while not self._stop_event.is_set():
            self.scan_callback()
            self._stop_event.wait(interval_seconds)
            time.sleep(0.05)
