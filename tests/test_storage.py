from boss_tool.storage import atomic_write_text


def test_atomic_write_text_writes_content_and_removes_temp_file(tmp_path) -> None:
    path = tmp_path / "settings.json"

    atomic_write_text(path, '{"ok": true}')

    assert path.read_text(encoding="utf-8") == '{"ok": true}'
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_text_replaces_existing_file(tmp_path) -> None:
    path = tmp_path / "history.json"
    path.write_text("old", encoding="utf-8")

    atomic_write_text(path, "new")

    assert path.read_text(encoding="utf-8") == "new"
