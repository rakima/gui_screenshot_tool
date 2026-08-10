import json

import pytest

from gui_screenshot_tool.config import SettingsError, SettingsStore
from gui_screenshot_tool.models import (
    AppSettings,
    AutoCaptureSettings,
    ExitMode,
    TitleMatchMode,
)


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


def test_auto_capture_profile_round_trip_preserves_manual_settings(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    manual = AppSettings("manual", str(tmp_path), "manual.png")
    automatic = AutoCaptureSettings(
        name="sample",
        command="python.exe",
        working_directory=str(tmp_path),
        arguments="app.py --demo",
        window_title="Sample App",
        title_match_mode=TitleMatchMode.PARTIAL,
        startup_timeout_seconds=10,
        capture_delay_seconds=0.5,
        output_directory=str(tmp_path / "images"),
        filename="sample.png",
        close_after_capture=True,
        exit_mode=ExitMode.GRACEFUL_THEN_FORCE,
        add_sequence_number=True,
    )

    store.save(manual)
    store.save_auto_capture_profile(automatic)

    assert store.get() == manual
    assert store.load_auto_capture_profiles() == {"sample": automatic}


def test_delete_auto_capture_profile(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    automatic = AutoCaptureSettings(
        "sample",
        "app.exe",
        str(tmp_path),
        "",
        "Sample",
        TitleMatchMode.EXACT,
        10,
        0,
        str(tmp_path),
        "sample.png",
        False,
        ExitMode.LEAVE_RUNNING,
    )
    store.save_auto_capture_profile(automatic)

    store.delete_auto_capture_profile("sample")

    assert store.load_auto_capture_profiles() == {}
