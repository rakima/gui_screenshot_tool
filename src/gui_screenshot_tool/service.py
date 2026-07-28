"""Application use cases shared by the CLI and GUI."""

from pathlib import Path

from gui_screenshot_tool.capture import CaptureError, capture_window
from gui_screenshot_tool.models import AppSettings, WindowInfo
from gui_screenshot_tool.windows import find_window


def validate_settings(settings: AppSettings) -> None:
    if not settings.window_title.strip():
        raise ValueError("対象ウィンドウを選択してください。")
    if not settings.output_directory.strip():
        raise ValueError("保存先を指定してください。")
    filename = settings.filename.strip()
    if not filename:
        raise ValueError("ファイル名を指定してください。")
    if Path(filename).name != filename:
        raise ValueError("ファイル名にはディレクトリを含めないでください。")
    if Path(filename).suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("対応する拡張子は .png、.jpg、.jpeg、.webp です。")


def capture_from_settings(settings: AppSettings) -> Path:
    validate_settings(settings)
    window = find_window(settings.window_title)
    if window is None:
        raise CaptureError(f"対象ウィンドウが見つかりません: {settings.window_title}")
    return capture_window(window.handle, settings.output_path)


def capture_selected(window: WindowInfo, settings: AppSettings) -> Path:
    validate_settings(settings)
    return capture_window(window.handle, settings.output_path)
