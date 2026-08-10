"""Application use cases shared by the CLI and GUI."""

import re
from pathlib import Path

from gui_screenshot_tool.capture import CaptureError, capture_window
from gui_screenshot_tool.models import AppSettings, AutoCaptureSettings, WindowInfo
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


def validate_auto_capture_settings(settings: AutoCaptureSettings) -> None:
    """Validate an automatic capture profile before saving or executing it."""
    if not settings.name.strip():
        raise ValueError("設定名を入力してください。")
    if not settings.command.strip():
        raise ValueError("実行コマンドを入力してください。")
    if not settings.working_directory.strip():
        raise ValueError("作業ディレクトリを入力してください。")
    if not settings.window_title.strip():
        raise ValueError("対象ウィンドウタイトルを入力してください。")
    if settings.startup_timeout_seconds <= 0:
        raise ValueError("最大起動待機時間は0より大きい値にしてください。")
    if settings.capture_delay_seconds < 0:
        raise ValueError("追加待機時間は0以上にしてください。")
    if settings.shutdown_timeout_seconds <= 0:
        raise ValueError("終了待機時間は0より大きい値にしてください。")
    validate_settings(
        AppSettings(
            window_title=settings.window_title,
            output_directory=settings.output_directory,
            filename=settings.filename,
        )
    )
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', settings.filename):
        raise ValueError("ファイル名にWindowsで使用できない文字が含まれています。")
    if settings.filename[-1:] in {" ", "."}:
        raise ValueError("ファイル名の末尾に空白またはピリオドは使用できません。")


def resolve_output_path(settings: AppSettings | AutoCaptureSettings) -> Path:
    """Resolve the destination path, adding the next sequence when enabled."""
    directory = Path(settings.output_directory)
    if not settings.add_sequence_number:
        return directory / settings.filename

    pattern = re.compile(rf"^(\d+)_{re.escape(settings.filename)}$")
    highest_sequence = 0
    if directory.is_dir():
        for candidate in directory.iterdir():
            match = pattern.match(candidate.name)
            if match:
                highest_sequence = max(highest_sequence, int(match.group(1)))
    return directory / f"{highest_sequence + 1:02d}_{settings.filename}"


def capture_from_settings(settings: AppSettings) -> Path:
    validate_settings(settings)
    window = find_window(settings.window_title)
    if window is None:
        raise CaptureError(f"対象ウィンドウが見つかりません: {settings.window_title}")
    return capture_window(window.handle, resolve_output_path(settings))


def capture_selected(window: WindowInfo, settings: AppSettings) -> Path:
    validate_settings(settings)
    return capture_window(window.handle, resolve_output_path(settings))
