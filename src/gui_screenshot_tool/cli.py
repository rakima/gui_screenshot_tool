"""Command-line interface."""

import argparse
import sys

from gui_screenshot_tool.capture import CaptureError, enable_dpi_awareness
from gui_screenshot_tool.config import SettingsError, SettingsStore
from gui_screenshot_tool.service import capture_from_settings
from gui_screenshot_tool.windows import WindowError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="選択したWindowsウィンドウのスクリーンショットを保存します。"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--configure",
        action="store_true",
        help="GUIを開いて対象ウィンドウや保存先を設定します。",
    )
    mode.add_argument(
        "--capture",
        action="store_true",
        help="保存済み設定を使い、GUIを開かずに撮影します。",
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="使用する設定名（既定: default）。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = SettingsStore()
    if not args.capture:
        from gui_screenshot_tool.gui import run_gui

        run_gui(store, args.profile)
        return 0

    enable_dpi_awareness()
    try:
        settings = store.get(args.profile)
        if settings is None:
            raise SettingsError(
                f"設定 '{args.profile}' がありません。先に --configure を実行してください。"
            )
        output_path = capture_from_settings(settings)
    except (SettingsError, CaptureError, WindowError, ValueError, OSError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    print(f"保存しました: {output_path}")
    return 0
