"""Win32 top-level window discovery."""

import sys
from collections.abc import Callable

from gui_screenshot_tool.models import WindowInfo


class WindowError(RuntimeError):
    """Raised when Windows APIs cannot be used."""


def _require_windows() -> None:
    if sys.platform != "win32":
        raise WindowError("この機能は Windows でのみ利用できます。")


def list_windows() -> list[WindowInfo]:
    """Return titled, visible top-level windows."""
    _require_windows()
    import win32gui

    windows: list[WindowInfo] = []

    def callback(handle: int, _extra: object) -> bool:
        title = win32gui.GetWindowText(handle).strip()
        visible = bool(win32gui.IsWindowVisible(handle))
        if title and visible and win32gui.GetParent(handle) == 0:
            windows.append(
                WindowInfo(
                    handle=handle,
                    title=title,
                    visible=visible,
                    minimized=bool(win32gui.IsIconic(handle)),
                )
            )
        return True

    enum_windows: Callable[[Callable[[int, object], bool], object], None] = win32gui.EnumWindows
    enum_windows(callback, None)
    return sorted(windows, key=lambda item: item.title.casefold())


def find_window(title: str) -> WindowInfo | None:
    """Find a usable window, preferring an exact title match."""
    windows = list_windows()
    exact = [window for window in windows if window.title.casefold() == title.casefold()]
    if exact:
        return exact[0]
    partial = [window for window in windows if title.casefold() in window.title.casefold()]
    return partial[0] if partial else None
