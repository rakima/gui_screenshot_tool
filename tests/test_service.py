from datetime import datetime
from pathlib import Path

import pytest

from gui_screenshot_tool.models import (
    AppSettings,
    AutoCaptureSettings,
    ExitMode,
    TitleMatchMode,
)
from gui_screenshot_tool.service import (
    resolve_output_path,
    validate_auto_capture_settings,
    validate_settings,
)


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


def test_sequence_number_starts_at_01(tmp_path):
    settings = make_auto_settings(tmp_path, add_sequence_number=True)

    assert resolve_output_path(settings) == tmp_path / "01_sample.png"


def test_sequence_number_uses_next_number_without_overwriting(tmp_path):
    (tmp_path / "01_sample.png").touch()
    (tmp_path / "02_sample.png").touch()
    (tmp_path / "unrelated.png").touch()
    settings = make_auto_settings(tmp_path, add_sequence_number=True)

    assert resolve_output_path(settings) == tmp_path / "03_sample.png"


def test_sequence_number_expands_beyond_two_digits(tmp_path):
    (tmp_path / "99_sample.png").touch()
    settings = make_auto_settings(tmp_path, add_sequence_number=True)

    assert resolve_output_path(settings) == tmp_path / "100_sample.png"


def test_timestamp_is_added_before_extension(tmp_path):
    settings = make_auto_settings(tmp_path, add_timestamp=True)

    assert resolve_output_path(
        settings,
        datetime(2026, 8, 10, 14, 30, 25),
    ) == (tmp_path / "sample_20260810143025.png")


def test_date_is_added_before_extension(tmp_path):
    settings = make_auto_settings(tmp_path, add_date=True)

    assert resolve_output_path(
        settings,
        datetime(2026, 8, 10, 14, 30, 25),
    ) == (tmp_path / "sample_20260810.png")


def test_date_and_timestamp_cannot_both_be_enabled(tmp_path):
    settings = make_auto_settings(tmp_path, add_date=True, add_timestamp=True)

    with pytest.raises(ValueError, match="同時に指定できません"):
        validate_auto_capture_settings(settings)


def test_sequence_and_timestamp_can_be_used_together(tmp_path):
    (tmp_path / "01_sample_20260809120000.png").touch()
    (tmp_path / "02_sample.png").touch()
    settings = make_auto_settings(
        tmp_path,
        add_sequence_number=True,
        add_timestamp=True,
    )

    assert resolve_output_path(
        settings,
        datetime(2026, 8, 10, 14, 30, 25),
    ) == (tmp_path / "03_sample_20260810143025.png")


def test_sequence_continues_across_date_and_datetime_modes(tmp_path):
    (tmp_path / "01_sample_20260809.png").touch()
    (tmp_path / "02_sample_20260809120000.png").touch()
    settings = make_auto_settings(
        tmp_path,
        add_sequence_number=True,
        add_date=True,
    )

    assert resolve_output_path(
        settings,
        datetime(2026, 8, 10, 14, 30, 25),
    ) == (tmp_path / "03_sample_20260810.png")
