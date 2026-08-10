"""Launch, detect, capture, and close a configured GUI application."""

import ctypes
import subprocess
import sys
import time
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path

from gui_screenshot_tool.capture import capture_window
from gui_screenshot_tool.models import AutoCaptureSettings, ExitMode, WindowInfo
from gui_screenshot_tool.service import resolve_output_path, validate_auto_capture_settings
from gui_screenshot_tool.windows import (
    bring_to_foreground,
    find_window_for_process,
    force_terminate_process,
    request_window_close,
    window_exists,
)

LogCallback = Callable[[str], None]


class AutomationError(RuntimeError):
    """Raised when an automatic capture workflow cannot complete."""


def parse_command_line_arguments(arguments: str) -> list[str]:
    """Parse Windows command-line text using the operating system's rules."""
    if not arguments.strip():
        return []
    if sys.platform != "win32":
        raise AutomationError("自動撮影は Windows でのみ利用できます。")

    argument_count = ctypes.c_int()
    command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(wintypes.LPWSTR)
    argv = command_line_to_argv(arguments, ctypes.byref(argument_count))
    if not argv:
        raise AutomationError("コマンドライン引数を解析できません。")
    try:
        return [argv[index] for index in range(argument_count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def launch_application(settings: AutoCaptureSettings) -> subprocess.Popen[bytes]:
    """Start the configured application and return its process handle."""
    working_directory = Path(settings.working_directory)
    if not working_directory.is_dir():
        raise AutomationError(f"作業ディレクトリが存在しません: {working_directory}")
    command = [settings.command, *parse_command_line_arguments(settings.arguments)]
    try:
        return subprocess.Popen(command, cwd=working_directory)
    except (OSError, ValueError) as exc:
        raise AutomationError(f"アプリを起動できません: {settings.command}") from exc


class AutoCaptureRunner:
    """Synchronous workflow runner intended to execute on a worker thread."""

    def __init__(
        self,
        *,
        launcher: Callable[[AutoCaptureSettings], subprocess.Popen[bytes]] = launch_application,
        window_finder: Callable[[str, int, object], WindowInfo | None] = (find_window_for_process),
        foreground_setter: Callable[[WindowInfo], None] = bring_to_foreground,
        capturer: Callable[[int, Path], Path] = capture_window,
        close_requester: Callable[[int], None] = request_window_close,
        existence_checker: Callable[[int], bool] = window_exists,
        force_terminator: Callable[[int], None] = force_terminate_process,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        poll_interval: float = 0.25,
    ) -> None:
        self.launcher = launcher
        self.window_finder = window_finder
        self.foreground_setter = foreground_setter
        self.capturer = capturer
        self.close_requester = close_requester
        self.existence_checker = existence_checker
        self.force_terminator = force_terminator
        self.sleeper = sleeper
        self.clock = clock
        self.poll_interval = poll_interval

    def run(self, settings: AutoCaptureSettings, log: LogCallback) -> Path:
        validate_auto_capture_settings(settings)
        process: subprocess.Popen[bytes] | None = None
        window: WindowInfo | None = None
        completed = False
        try:
            log(f"起動します: {settings.command} {settings.arguments}".rstrip())
            process = self.launcher(settings)
            log(f"プロセスを起動しました (PID: {process.pid})。")
            window = self._wait_for_window(settings, process.pid, log)
            log(f"対象ウィンドウを検出しました: {window.title} (PID: {window.process_id})")
            if settings.capture_delay_seconds:
                log(f"撮影前に {settings.capture_delay_seconds:g} 秒待機します。")
                self.sleeper(settings.capture_delay_seconds)
            self.foreground_setter(window)
            log("対象ウィンドウを最前面にしました。")
            output_path = self.capturer(window.handle, resolve_output_path(settings))
            log(f"保存しました: {output_path.resolve()}")
            self._close_application(settings, process, window, log)
            completed = True
            log("自動撮影が完了しました。")
            return output_path
        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(str(exc) or exc.__class__.__name__) from exc
        finally:
            if not completed and process is not None:
                self._cleanup_after_failure(settings, process, window, log)

    def _wait_for_window(
        self,
        settings: AutoCaptureSettings,
        process_id: int,
        log: LogCallback,
    ) -> WindowInfo:
        deadline = self.clock() + settings.startup_timeout_seconds
        log(f"対象ウィンドウを待機します（最大 {settings.startup_timeout_seconds:g} 秒）。")
        while self.clock() < deadline:
            window = self.window_finder(
                settings.window_title,
                process_id,
                settings.title_match_mode,
            )
            if window is not None:
                return window
            self.sleeper(self.poll_interval)
        raise AutomationError(f"対象ウィンドウが見つかりません: {settings.window_title}")

    def _close_application(
        self,
        settings: AutoCaptureSettings,
        process: subprocess.Popen[bytes],
        window: WindowInfo,
        log: LogCallback,
    ) -> None:
        if not settings.close_after_capture or settings.exit_mode is ExitMode.LEAVE_RUNNING:
            log("設定に従い、アプリを終了せずに残します。")
            return

        log("アプリへ正常終了を要求します。")
        self.close_requester(window.handle)
        deadline = self.clock() + settings.shutdown_timeout_seconds
        while self.clock() < deadline:
            if process.poll() is not None or not self.existence_checker(window.handle):
                log("アプリが正常終了しました。")
                return
            self.sleeper(self.poll_interval)

        if settings.exit_mode is ExitMode.GRACEFUL:
            raise AutomationError("アプリを正常終了できませんでした。")

        log("終了待機時間を超えたため、アプリを強制終了します。")
        self.force_terminator(window.process_id or process.pid)
        log("アプリを強制終了しました。")

    def _cleanup_after_failure(
        self,
        settings: AutoCaptureSettings,
        process: subprocess.Popen[bytes],
        window: WindowInfo | None,
        log: LogCallback,
    ) -> None:
        if (
            not settings.close_after_capture
            or settings.exit_mode is ExitMode.LEAVE_RUNNING
            or process.poll() is not None
        ):
            return
        try:
            if window is not None:
                self.close_requester(window.handle)
            if settings.exit_mode is ExitMode.GRACEFUL_THEN_FORCE:
                self.force_terminator(
                    window.process_id if window and window.process_id else process.pid
                )
            log("失敗後のアプリ終了処理を実行しました。")
        except Exception as exc:
            log(f"失敗後のアプリ終了処理にも失敗しました: {exc}")
