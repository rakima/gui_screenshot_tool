"""Capture a single Windows window to an image file."""

import ctypes
import sys
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path


class CaptureError(RuntimeError):
    """Raised when a window cannot be captured."""


def enable_dpi_awareness() -> None:
    """Avoid scaled coordinates on high-DPI displays."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        with suppress(AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def capture_window(handle: int, output_path: Path) -> Path:
    """Capture *handle* with PrintWindow and overwrite *output_path*."""
    if sys.platform != "win32":
        raise CaptureError("スクリーンショット撮影は Windows でのみ利用できます。")

    import win32gui
    import win32ui
    from PIL import Image

    if not win32gui.IsWindow(handle):
        raise CaptureError("対象ウィンドウが存在しません。")
    if win32gui.IsIconic(handle):
        raise CaptureError("最小化されたウィンドウは撮影できません。復元して再試行してください。")

    left, top, right, bottom = win32gui.GetWindowRect(handle)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise CaptureError("対象ウィンドウのサイズを取得できません。")

    window_dc = win32gui.GetWindowDC(handle)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source_dc, width, height)
    memory_dc.SelectObject(bitmap)

    try:
        # PW_RENDERFULLCONTENT captures modern windows more reliably on Windows 8.1+.
        print_window = ctypes.windll.user32.PrintWindow
        print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        print_window.restype = wintypes.BOOL
        success = print_window(handle, memory_dc.GetSafeHdc(), 2)
        if not success:
            raise CaptureError(
                "ウィンドウの撮影に失敗しました。アプリによっては撮影が制限されています。"
            )
        bitmap_info = bitmap.GetInfo()
        bitmap_bytes = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bitmap_info["bmWidth"], bitmap_info["bmHeight"]),
            bitmap_bytes,
            "raw",
            "BGRX",
            0,
            1,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path
    except OSError as exc:
        raise CaptureError(f"画像を保存できません: {output_path}") from exc
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(handle, window_dc)
