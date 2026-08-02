from pathlib import Path

import pytest

from gui_screenshot_tool.models import (
    AppSettings,
    AutoCaptureSettings,
    ExitMode,
    TitleMatchMode,
)
from gui_screenshot_tool.service import validate_auto_capture_settings, validate_settings


def make_settings(filename: str = "main_window.png") -> AppSettings:
    return AppSettings("compare_tool", str(Path("docs") / "images"), filename)


@pytest.mark.parametrize("filename", ["shot.png", "shot.jpg", "shot.jpeg", "shot.webp"])
def test_supported_filenames(filename):
    validate_settings(make_settings(filename))


@pytest.mark.parametrize("filename", ["", "shot.bmp", "../shot.png"])
def test_invalid_filenames(filename):
    with pytest.raises(ValueError):
        validate_settings(make_settings(filename))


def make_auto_settings(tmp_path, **changes):
    values = {
        "name": "sample",
        "command": "app.exe",
        "working_directory": str(tmp_path),
        "arguments": "",
        "window_title": "Sample",
        "title_match_mode": TitleMatchMode.EXACT,
        "startup_timeout_seconds": 10,
        "capture_delay_seconds": 0,
        "output_directory": str(tmp_path),
        "filename": "sample.png",
        "close_after_capture": True,
        "exit_mode": ExitMode.GRACEFUL,
    }
    values.update(changes)
    return AutoCaptureSettings(**values)


def test_valid_auto_capture_settings(tmp_path):
    validate_auto_capture_settings(make_auto_settings(tmp_path))


@pytest.mark.parametrize("filename", ["bad:name.png", "bad?.png", "bad ."])
def test_auto_capture_rejects_windows_invalid_filename(tmp_path, filename):
    with pytest.raises(ValueError):
        validate_auto_capture_settings(make_auto_settings(tmp_path, filename=filename))
