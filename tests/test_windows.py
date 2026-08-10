import sys
from types import SimpleNamespace

import pytest

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


def test_list_windows_includes_owned_top_level_dialog(monkeypatch):
    fake_gui = SimpleNamespace(
        EnumWindows=lambda callback, extra: callback(10, extra),
        GetWindowText=lambda _handle: "Sample App",
        IsWindowVisible=lambda _handle: True,
        IsIconic=lambda _handle: False,
    )
    fake_process = SimpleNamespace(
        GetWindowThreadProcessId=lambda _handle: (20, 1234),
    )
    monkeypatch.setitem(sys.modules, "win32gui", fake_gui)
    monkeypatch.setitem(sys.modules, "win32process", fake_process)

    result = windows.list_windows()

    assert result == [WindowInfo(10, "Sample App", True, False, 1234)]


def test_missing_pywin32_reports_interpreter_and_install_command(monkeypatch):
    def missing(_name):
        raise ModuleNotFoundError("win32gui")

    monkeypatch.setattr(windows, "import_module", missing)

    with pytest.raises(windows.WindowError) as error:
        windows.list_windows()

    message = str(error.value)
    assert sys.executable in message
    assert "pip install pywin32" in message
