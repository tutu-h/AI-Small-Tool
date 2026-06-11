from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path

from boss_tool.storage import atomic_write_text


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass(slots=True)
class AppConfig:
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    text_model: str = "qwen-plus"
    vision_model: str = "qwen-vl-ocr"
    monitor_interval_seconds: int = 5
    boss_window_keyword: str = "BOSS"
    prefer_vision_for_web: bool = True


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppConfig()
        if not isinstance(payload, dict):
            return AppConfig()
        allowed_fields = {field.name for field in fields(AppConfig)}
        cleaned = {
            key: value
            for key, value in payload.items()
            if key in allowed_fields
        }
        return sanitize_config(AppConfig(**cleaned))

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        config = sanitize_config(config)
        atomic_write_text(
            self.path,
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
        )


def sanitize_config(config: AppConfig) -> AppConfig:
    defaults = AppConfig()
    return AppConfig(
        base_url=_clean_string(config.base_url, defaults.base_url),
        api_key=str(config.api_key or "").strip(),
        text_model=_clean_string(config.text_model, defaults.text_model),
        vision_model=_clean_string(config.vision_model, defaults.vision_model),
        monitor_interval_seconds=_clean_interval(
            config.monitor_interval_seconds,
            defaults.monitor_interval_seconds,
        ),
        boss_window_keyword=_clean_string(
            config.boss_window_keyword,
            defaults.boss_window_keyword,
        ),
        prefer_vision_for_web=_clean_bool(config.prefer_vision_for_web),
    )


def _clean_string(value, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _clean_interval(value, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(60, max(2, number))


def _clean_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "是"}
    return bool(value)
