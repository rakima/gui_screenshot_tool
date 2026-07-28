from pathlib import Path

import pytest

from gui_screenshot_tool.models import AppSettings
from gui_screenshot_tool.service import validate_settings


def make_settings(filename: str = "main_window.png") -> AppSettings:
    return AppSettings("compare_tool", str(Path("docs") / "images"), filename)


@pytest.mark.parametrize("filename", ["shot.png", "shot.jpg", "shot.jpeg", "shot.webp"])
def test_supported_filenames(filename):
    validate_settings(make_settings(filename))


@pytest.mark.parametrize("filename", ["", "shot.bmp", "../shot.png"])
def test_invalid_filenames(filename):
    with pytest.raises(ValueError):
        validate_settings(make_settings(filename))
