"""Capture a single Windows window to an image file."""

import ctypes
import sys
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path


class CaptureError(RuntimeError):
    """Raised when a window cannot be captured."""


def _visible_frame_crop(
    handle: int,
    window_rect: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    """Return a crop box that removes Windows' invisible resize border."""
    frame_rect = wintypes.RECT()
    dwm_get_window_attribute = ctypes.windll.dwmapi.DwmGetWindowAttribute
    dwm_get_window_attribute.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    dwm_get_window_attribute.restype = ctypes.c_long
    # DWMWA_EXTENDED_FRAME_BOUNDS (9) is the visible window frame in screen
    # coordinates, excluding the invisible resize border returned by GetWindowRect.
    result = dwm_get_window_attribute(
        handle,
        9,
        ctypes.byref(frame_rect),
        ctypes.sizeof(frame_rect),
    )
    if result != 0:
        return None

    window_left, window_top, _, _ = window_rect
    image_width, image_height = image_size
    crop = (
        max(0, frame_rect.left - window_left),
        max(0, frame_rect.top - window_top),
        min(image_width, frame_rect.right - window_left),
        min(image_height, frame_rect.bottom - window_top),
    )
    if crop[0] >= crop[2] or crop[1] >= crop[3]:
        return None
    return crop


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

    window_rect = win32gui.GetWindowRect(handle)
    left, top, right, bottom = window_rect
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
        with suppress(AttributeError, OSError):
            crop = _visible_frame_crop(handle, window_rect, image.size)
            if crop is not None and crop != (0, 0, *image.size):
                image = image.crop(crop)
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
