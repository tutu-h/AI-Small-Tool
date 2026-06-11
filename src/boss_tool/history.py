from __future__ import annotations

import json
from pathlib import Path

from boss_tool.exporter import snapshot_from_dict, snapshot_to_dict
from boss_tool.models import ScanSnapshot
from boss_tool.storage import atomic_write_text


class HistoryStore:
    def __init__(self, path: str | Path, limit: int = 20) -> None:
        self.path = Path(path)
        self.limit = limit

    def load(self) -> list[ScanSnapshot]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        snapshots = payload.get("snapshots", []) if isinstance(payload, dict) else []
        loaded: list[ScanSnapshot] = []
        for item in snapshots[-self.limit :]:
            if not isinstance(item, dict):
                continue
            try:
                loaded.append(snapshot_from_dict(item))
            except Exception:
                continue
        return loaded

    def save(self, snapshots: list[ScanSnapshot]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        recent = snapshots[-self.limit :]
        atomic_write_text(
            self.path,
            json.dumps(
                {"snapshots": [snapshot_to_dict(snapshot) for snapshot in recent]},
                ensure_ascii=False,
                indent=2,
            ),
        )
