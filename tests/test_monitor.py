from __future__ import annotations

from boss_tool.monitor import MonitorController


def test_monitor_callback_runs_on_background_thread() -> None:
    calls: list[str] = []

    def callback() -> None:
        calls.append("tick")

    monitor = MonitorController(callback)
    monitor.start(1)
    monitor.stop()

    assert monitor._thread is not None
    assert monitor._thread.daemon is True
