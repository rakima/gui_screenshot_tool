import json

import pytest

from gui_screenshot_tool.config import SettingsError, SettingsStore
from gui_screenshot_tool.models import AppSettings


def test_missing_settings_returns_empty(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")

    assert store.load_all() == {}
    assert store.get() is None


def test_settings_round_trip(tmp_path):
    path = tmp_path / "nested" / "settings.json"
    store = SettingsStore(path)
    settings = AppSettings(
        window_title="compare_tool",
        output_directory=r"C:\work\compare_tool\docs\images",
        filename="main_window.png",
    )

    store.save(settings)

    assert store.get() == settings
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["apps"]["default"]["filename"] == "main_window.png"


def test_invalid_json_raises_settings_error(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(SettingsError):
        SettingsStore(path).load_all()
