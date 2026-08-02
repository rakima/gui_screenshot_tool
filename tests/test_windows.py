import sys
from types import SimpleNamespace

from gui_screenshot_tool import windows
from gui_screenshot_tool.models import TitleMatchMode, WindowInfo


def test_find_window_prefers_launched_process_over_existing_same_title(monkeypatch):
    existing = WindowInfo(1, "Sample App", True, False, 100)
    launched = WindowInfo(2, "Sample App", True, False, 200)
    monkeypatch.setattr(windows, "list_windows", lambda: [existing, launched])
    monkeypatch.setitem(
        sys.modules,
        "win32gui",
        SimpleNamespace(GetWindowRect=lambda handle: (0, 0, 800 + handle, 600)),
    )

    result = windows.find_window_for_process("Sample App", 200, TitleMatchMode.EXACT)

    assert result == launched


def test_find_window_supports_partial_title_match(monkeypatch):
    target = WindowInfo(2, "Sample App - document.txt", True, False, 200)
    monkeypatch.setattr(windows, "list_windows", lambda: [target])
    monkeypatch.setitem(
        sys.modules,
        "win32gui",
        SimpleNamespace(GetWindowRect=lambda _handle: (0, 0, 800, 600)),
    )

    result = windows.find_window_for_process("Sample App", 200, TitleMatchMode.PARTIAL)

    assert result == target
