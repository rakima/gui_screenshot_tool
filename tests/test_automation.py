import pytest

from gui_screenshot_tool.automation import (
    AutoCaptureRunner,
    AutomationError,
    launch_application,
    parse_command_line_arguments,
)
from gui_screenshot_tool.models import (
    AutoCaptureSettings,
    ExitMode,
    TitleMatchMode,
    WindowInfo,
)


class FakeProcess:
    pid = 1234

    def __init__(self, return_code=None):
        self.return_code = return_code

    def poll(self):
        return self.return_code


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_settings(tmp_path, **changes):
    values = {
        "name": "sample",
        "command": "sample.exe",
        "working_directory": str(tmp_path),
        "arguments": "--demo",
        "window_title": "Sample App",
        "title_match_mode": TitleMatchMode.EXACT,
        "startup_timeout_seconds": 2,
        "capture_delay_seconds": 0,
        "output_directory": str(tmp_path / "new" / "images"),
        "filename": "sample.png",
        "close_after_capture": True,
        "exit_mode": ExitMode.GRACEFUL,
        "shutdown_timeout_seconds": 1,
    }
    values.update(changes)
    return AutoCaptureSettings(**values)


def test_successful_launch_capture_save_and_graceful_close(tmp_path):
    fake_time = FakeTime()
    process = FakeProcess()
    window = WindowInfo(10, "Sample App", True, False, process.pid)
    events = []
    output_path = tmp_path / "new" / "images" / "sample.png"

    def capture(handle, path):
        assert handle == window.handle
        assert path == output_path
        path.parent.mkdir(parents=True)
        path.write_bytes(b"png")
        return path

    runner = AutoCaptureRunner(
        launcher=lambda _settings: process,
        window_finder=lambda *_args: window,
        foreground_setter=lambda selected: events.append(("foreground", selected.handle)),
        capturer=capture,
        close_requester=lambda handle: events.append(("close", handle)),
        existence_checker=lambda _handle: False,
        sleeper=fake_time.sleep,
        clock=fake_time.clock,
    )

    result = runner.run(make_settings(tmp_path), events.append)

    assert result == output_path
    assert output_path.exists()
    assert ("foreground", window.handle) in events
    assert ("close", window.handle) in events


def test_invalid_launch_command_is_reported(tmp_path):
    def fail(_settings):
        raise AutomationError("アプリを起動できません: missing.exe")

    runner = AutoCaptureRunner(launcher=fail)

    with pytest.raises(AutomationError, match="起動できません"):
        runner.run(make_settings(tmp_path), lambda _message: None)


def test_launch_application_rejects_missing_command(tmp_path):
    settings = make_settings(
        tmp_path,
        command=str(tmp_path / "missing.exe"),
        arguments="",
    )

    with pytest.raises(AutomationError, match="起動できません"):
        launch_application(settings)


def test_windows_command_line_arguments_support_quoted_values():
    assert parse_command_line_arguments('--mode demo --title "Hello world"') == [
        "--mode",
        "demo",
        "--title",
        "Hello world",
    ]


def test_window_timeout_closes_launched_process(tmp_path):
    fake_time = FakeTime()
    process = FakeProcess()
    forced = []
    runner = AutoCaptureRunner(
        launcher=lambda _settings: process,
        window_finder=lambda *_args: None,
        force_terminator=forced.append,
        sleeper=fake_time.sleep,
        clock=fake_time.clock,
        poll_interval=0.5,
    )

    with pytest.raises(AutomationError, match="見つかりません"):
        runner.run(
            make_settings(tmp_path, exit_mode=ExitMode.GRACEFUL_THEN_FORCE),
            lambda _message: None,
        )

    assert forced == [process.pid]


def test_force_terminates_when_graceful_close_times_out(tmp_path):
    fake_time = FakeTime()
    process = FakeProcess()
    window = WindowInfo(10, "Sample App", True, False, process.pid)
    forced = []
    runner = AutoCaptureRunner(
        launcher=lambda _settings: process,
        window_finder=lambda *_args: window,
        foreground_setter=lambda _window: None,
        capturer=lambda _handle, path: path,
        close_requester=lambda _handle: None,
        existence_checker=lambda _handle: True,
        force_terminator=forced.append,
        sleeper=fake_time.sleep,
        clock=fake_time.clock,
        poll_interval=0.5,
    )

    runner.run(
        make_settings(tmp_path, exit_mode=ExitMode.GRACEFUL_THEN_FORCE),
        lambda _message: None,
    )

    assert forced == [process.pid]


def test_graceful_only_reports_failure_when_app_does_not_exit(tmp_path):
    fake_time = FakeTime()
    process = FakeProcess()
    window = WindowInfo(10, "Sample App", True, False, process.pid)
    runner = AutoCaptureRunner(
        launcher=lambda _settings: process,
        window_finder=lambda *_args: window,
        foreground_setter=lambda _window: None,
        capturer=lambda _handle, path: path,
        close_requester=lambda _handle: None,
        existence_checker=lambda _handle: True,
        sleeper=fake_time.sleep,
        clock=fake_time.clock,
        poll_interval=0.5,
    )

    with pytest.raises(AutomationError, match="正常終了できません"):
        runner.run(make_settings(tmp_path), lambda _message: None)


def test_leave_running_does_not_request_close(tmp_path):
    process = FakeProcess()
    window = WindowInfo(10, "Sample App", True, False, process.pid)
    close_requests = []
    runner = AutoCaptureRunner(
        launcher=lambda _settings: process,
        window_finder=lambda *_args: window,
        foreground_setter=lambda _window: None,
        capturer=lambda _handle, path: path,
        close_requester=close_requests.append,
    )

    runner.run(
        make_settings(
            tmp_path,
            close_after_capture=False,
            exit_mode=ExitMode.LEAVE_RUNNING,
        ),
        lambda _message: None,
    )

    assert close_requests == []
