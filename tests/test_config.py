from pathlib import Path

from boss_tool.config import AppConfig, ConfigStore, sanitize_config


def test_config_store_round_trips_models_and_api_key(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "settings.json")
    original = AppConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="secret",
        text_model="qwen-plus",
        vision_model="qwen-vl-ocr",
        monitor_interval_seconds=5,
        boss_window_keyword="Boss",
    )

    store.save(original)
    loaded = store.load()

    assert loaded == original


def test_config_store_returns_default_for_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{bad json", encoding="utf-8")

    loaded = ConfigStore(path).load()

    assert loaded == AppConfig()


def test_config_store_ignores_unknown_fields_and_fills_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"api_key": "secret", "old_field": "ignored"}',
        encoding="utf-8",
    )

    loaded = ConfigStore(path).load()

    assert loaded.api_key == "secret"
    assert loaded.base_url == AppConfig().base_url
    assert not hasattr(loaded, "old_field")


def test_config_store_sanitizes_invalid_field_types_and_ranges(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        (
            '{"base_url": "", "text_model": "", "vision_model": "", '
            '"monitor_interval_seconds": "abc", '
            '"boss_window_keyword": "", "prefer_vision_for_web": "no"}'
        ),
        encoding="utf-8",
    )

    loaded = ConfigStore(path).load()

    assert loaded.base_url == AppConfig().base_url
    assert loaded.text_model == AppConfig().text_model
    assert loaded.vision_model == AppConfig().vision_model
    assert loaded.monitor_interval_seconds == AppConfig().monitor_interval_seconds
    assert loaded.boss_window_keyword == "BOSS"
    assert loaded.prefer_vision_for_web is False


def test_sanitize_config_clamps_monitor_interval() -> None:
    config = AppConfig(monitor_interval_seconds=1)

    sanitized = sanitize_config(config)

    assert sanitized.monitor_interval_seconds == 2
