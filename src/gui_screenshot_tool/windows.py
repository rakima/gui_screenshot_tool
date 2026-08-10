"""Win32 top-level window discovery."""

import sys
from collections.abc import Callable
from importlib import import_module
from typing import Any

from gui_screenshot_tool.models import TitleMatchMode, WindowInfo


class WindowError(RuntimeError):
    """Raised when Windows APIs cannot be used."""


def _require_windows() -> None:
    if sys.platform != "win32":
        raise WindowError("この機能は Windows でのみ利用できます。")


def _load_pywin32_modules(*names: str) -> tuple[Any, ...]:
    """Load pywin32 modules or raise an actionable application error."""
    try:
        return tuple(import_module(name) for name in names)
    except ModuleNotFoundError as exc:
        command = f'"{sys.executable}" -m pip install pywin32'
        raise WindowError(
            "Windows操作に必要な pywin32 が、このPython環境にインストールされて"
            f"いません。\n実行中のPython: {sys.executable}\n"
            f"インストールコマンド: {command}"
        ) from exc


def list_windows() -> list[WindowInfo]:
    """Return titled, visible top-level windows."""
    _require_windows()
    win32gui, win32process = _load_pywin32_modules("win32gui", "win32process")

    windows: list[WindowInfo] = []

    def callback(handle: int, _extra: object) -> bool:
        title = win32gui.GetWindowText(handle).strip()
        visible = bool(win32gui.IsWindowVisible(handle))
        # EnumWindows already limits results to top-level windows. An owned
        # top-level window (for example a Tkinter Toplevel dialog) may have a
        # non-zero GetParent result, so do not exclude it here.
        if title and visible:
            _, process_id = win32process.GetWindowThreadProcessId(handle)
            windows.append(
                WindowInfo(
                    handle=handle,
                    title=title,
                    visible=visible,
                    minimized=bool(win32gui.IsIconic(handle)),
                    process_id=process_id,
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


def find_window_for_process(
    title: str,
    process_id: int,
    match_mode: TitleMatchMode,
) -> WindowInfo | None:
    """Find a target window, preferring one owned by the launched process."""
    normalized = title.casefold()

    def title_matches(window: WindowInfo) -> bool:
        candidate = window.title.casefold()
        if match_mode is TitleMatchMode.EXACT:
            return candidate == normalized
        return normalized in candidate

    candidates = [
        window for window in list_windows() if not window.minimized and title_matches(window)
    ]
    if not candidates:
        return None

    (win32gui,) = _load_pywin32_modules("win32gui")

    def rank(window: WindowInfo) -> tuple[bool, bool, int]:
        left, top, right, bottom = win32gui.GetWindowRect(window.handle)
        area = max(0, right - left) * max(0, bottom - top)
        return (
            window.process_id == process_id,
            window.title.casefold() == normalized,
            area,
        )

    return max(candidates, key=rank)


def bring_to_foreground(window: WindowInfo) -> None:
    """Restore and bring a window to the foreground."""
    _require_windows()
    win32con, win32gui = _load_pywin32_modules("win32con", "win32gui")

    if not win32gui.IsWindow(window.handle):
        raise WindowError("対象ウィンドウが存在しません。")
    if win32gui.IsIconic(window.handle):
        win32gui.ShowWindow(window.handle, win32con.SW_RESTORE)
    try:
        win32gui.BringWindowToTop(window.handle)
        win32gui.SetForegroundWindow(window.handle)
    except win32gui.error as exc:
        raise WindowError("対象ウィンドウを最前面にできません。") from exc


def request_window_close(handle: int) -> None:
    """Post a normal WM_CLOSE request to a window."""
    _require_windows()
    win32con, win32gui = _load_pywin32_modules("win32con", "win32gui")

    if win32gui.IsWindow(handle):
        win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)


def window_exists(handle: int) -> bool:
    _require_windows()
    (win32gui,) = _load_pywin32_modules("win32gui")

    return bool(win32gui.IsWindow(handle))


def force_terminate_process(process_id: int) -> None:
    """Forcefully terminate a process by PID."""
    _require_windows()
    win32api, win32con = _load_pywin32_modules("win32api", "win32con")

    process_handle = None
    try:
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_TERMINATE,
            False,
            process_id,
        )
        win32api.TerminateProcess(process_handle, 1)
    except Exception as exc:
        raise WindowError(f"プロセスを強制終了できません (PID: {process_id})。") from exc
    finally:
        if process_handle is not None:
            process_handle.Close()
