"""Tkinter user interface."""

import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from gui_screenshot_tool.automation import (
    AutoCaptureRunner,
    AutomationError,
    launch_application,
)
from gui_screenshot_tool.capture import CaptureError, enable_dpi_awareness
from gui_screenshot_tool.config import SettingsError, SettingsStore
from gui_screenshot_tool.models import (
    AppSettings,
    AutoCaptureSettings,
    ExitMode,
    TitleMatchMode,
    WindowInfo,
)
from gui_screenshot_tool.service import (
    capture_selected,
    validate_auto_capture_settings,
    validate_settings,
)
from gui_screenshot_tool.windows import WindowError, list_windows

DATE_SUFFIX_NONE = "none"
DATE_SUFFIX_DATE = "date"
DATE_SUFFIX_DATETIME = "datetime"


def run_in_background(target: Callable[[], None], name: str) -> threading.Thread:
    """Start work without blocking or accessing Tk from the worker."""
    worker = threading.Thread(target=target, daemon=True, name=name)
    worker.start()
    return worker


class ScreenshotApp(ttk.Frame):
    """Main configuration and capture view."""

    def __init__(self, master: tk.Tk, store: SettingsStore, profile: str = "default") -> None:
        super().__init__(master, padding=18)
        self.master = master
        self.store = store
        self.profile = profile
        self.windows: list[WindowInfo] = []
        self.window_var = tk.StringVar()
        self.directory_var = tk.StringVar()
        self.filename_var = tk.StringVar(value="screenshot.png")
        self.sequence_var = tk.BooleanVar(value=False)
        self.date_suffix_var = tk.StringVar(value=DATE_SUFFIX_NONE)
        self.status_var = tk.StringVar(value="ウィンドウ一覧を読み込んでいます…")
        self._build()
        self._load_settings()
        # EnumWindows only reports this application after Tk has mapped the root
        # window. Delaying the initial refresh also makes this tool selectable as
        # a README screenshot target.
        self.master.after(100, self.refresh_windows)

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="対象ウィンドウ").grid(row=0, column=0, sticky="w")
        window_row = ttk.Frame(self)
        window_row.grid(row=1, column=0, sticky="ew", pady=(4, 14))
        window_row.columnconfigure(0, weight=1)
        self.window_combo = ttk.Combobox(
            window_row,
            textvariable=self.window_var,
            state="readonly",
            width=64,
        )
        self.window_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(window_row, text="更新", command=self.refresh_windows).grid(
            row=0, column=1, padx=(8, 0)
        )

        ttk.Label(self, text="保存先").grid(row=2, column=0, sticky="w")
        directory_row = ttk.Frame(self)
        directory_row.grid(row=3, column=0, sticky="ew", pady=(4, 14))
        directory_row.columnconfigure(0, weight=1)
        ttk.Entry(directory_row, textvariable=self.directory_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(directory_row, text="参照…", command=self.choose_directory).grid(
            row=0, column=1, padx=(8, 0)
        )

        ttk.Label(self, text="ファイル名").grid(row=4, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.filename_var).grid(
            row=5, column=0, sticky="ew", pady=(4, 8)
        )
        ttk.Checkbutton(
            self,
            text="ファイル名の先頭に連番を付ける（01_、02_…）",
            variable=self.sequence_var,
        ).grid(row=6, column=0, sticky="w", pady=(0, 18))
        date_suffix_row = ttk.Frame(self)
        date_suffix_row.grid(row=7, column=0, sticky="w", pady=(0, 18))
        ttk.Label(date_suffix_row, text="日付の付加:").grid(row=0, column=0, padx=(0, 8))
        for column, (label, value) in enumerate(
            (
                ("なし", DATE_SUFFIX_NONE),
                ("日付（YYYYMMDD）", DATE_SUFFIX_DATE),
                ("日時（YYYYMMDDHHMMSS）", DATE_SUFFIX_DATETIME),
            ),
            start=1,
        ):
            ttk.Radiobutton(
                date_suffix_row,
                text=label,
                value=value,
                variable=self.date_suffix_var,
            ).grid(row=0, column=column, padx=(0, 8))

        buttons = ttk.Frame(self)
        buttons.grid(row=8, column=0, sticky="e")
        ttk.Button(buttons, text="設定保存", command=self.save_settings).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(
            buttons,
            text="スクリーンショット撮影",
            command=self.capture,
            style="Accent.TButton",
        ).grid(row=0, column=1)
        ttk.Separator(self).grid(row=9, column=0, sticky="ew", pady=(18, 10))
        ttk.Label(self, textvariable=self.status_var).grid(row=10, column=0, sticky="w")

    def _load_settings(self) -> None:
        try:
            settings = self.store.get(self.profile)
        except SettingsError as exc:
            messagebox.showerror("設定エラー", str(exc))
            return
        if settings:
            self.window_var.set(settings.window_title)
            self.directory_var.set(settings.output_directory)
            self.filename_var.set(settings.filename)
            self.sequence_var.set(settings.add_sequence_number)
            if settings.add_timestamp:
                self.date_suffix_var.set(DATE_SUFFIX_DATETIME)
            elif settings.add_date:
                self.date_suffix_var.set(DATE_SUFFIX_DATE)
            else:
                self.date_suffix_var.set(DATE_SUFFIX_NONE)

    def refresh_windows(self) -> None:
        remembered_title = self._selected_title() or self.window_var.get()
        try:
            self.windows = list_windows()
        except WindowError as exc:
            messagebox.showerror("ウィンドウ取得エラー", str(exc))
            self.status_var.set("ウィンドウ一覧を取得できませんでした。")
            return
        display_names = [window.display_name for window in self.windows]
        self.window_combo["values"] = display_names
        match = next(
            (
                window
                for window in self.windows
                if window.title.casefold() == remembered_title.casefold()
            ),
            None,
        )
        if match:
            self.window_var.set(match.display_name)
        elif self.windows and not self.window_var.get():
            self.window_var.set(self.windows[0].display_name)
        self.status_var.set(f"{len(self.windows)} 件のウィンドウを取得しました。")

    def _selected_window(self) -> WindowInfo | None:
        selected = self.window_var.get()
        return next(
            (window for window in self.windows if window.display_name == selected),
            None,
        )

    def _selected_title(self) -> str:
        window = self._selected_window()
        return window.title if window else self.window_var.get()

    def _settings(self) -> AppSettings:
        return AppSettings(
            window_title=self._selected_title().strip(),
            output_directory=self.directory_var.get().strip(),
            filename=self.filename_var.get().strip(),
            add_sequence_number=self.sequence_var.get(),
            add_timestamp=self.date_suffix_var.get() == DATE_SUFFIX_DATETIME,
            add_date=self.date_suffix_var.get() == DATE_SUFFIX_DATE,
        )

    def choose_directory(self) -> None:
        initial = self.directory_var.get()
        selected = filedialog.askdirectory(
            title="保存先を選択",
            initialdir=initial if Path(initial).is_dir() else None,
        )
        if selected:
            self.directory_var.set(selected)

    def save_settings(self, *, show_confirmation: bool = True) -> bool:
        try:
            settings = self._settings()
            validate_settings(settings)
            self.store.save(settings, self.profile)
        except (ValueError, SettingsError) as exc:
            messagebox.showerror("設定エラー", str(exc))
            return False
        self.status_var.set(f"設定を保存しました: {self.store.path}")
        if show_confirmation:
            messagebox.showinfo("設定保存", "設定を保存しました。")
        return True

    def capture(self) -> None:
        window = self._selected_window()
        if window is None:
            messagebox.showerror(
                "撮影エラー",
                "対象ウィンドウを一覧から選択してください。一覧を更新すると再取得できます。",
            )
            return
        if not self.save_settings(show_confirmation=False):
            return
        try:
            output_path = capture_selected(window, self._settings())
        except (CaptureError, ValueError, OSError) as exc:
            messagebox.showerror("撮影エラー", str(exc))
            self.status_var.set("撮影に失敗しました。")
            return
        self.status_var.set(f"保存しました: {output_path}")
        messagebox.showinfo("撮影完了", f"保存しました。\n{output_path}")


class AutoCaptureFrame(ttk.Frame):
    """Run registered automatic capture profiles without blocking Tk."""

    def __init__(self, master: ttk.Notebook, store: SettingsStore) -> None:
        super().__init__(master, padding=18)
        self.store = store
        self.runner = AutoCaptureRunner()
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build()
        self.refresh_profiles()
        self.after(100, self._drain_messages)

    def _build(self) -> None:
        ttk.Label(self, text="登録済み設定").grid(row=0, column=0, sticky="w")
        self.profile_tree = ttk.Treeview(
            self,
            columns=("command", "window", "output"),
            show="tree headings",
            height=7,
        )
        self.profile_tree.heading("#0", text="設定名")
        self.profile_tree.heading("command", text="実行コマンド")
        self.profile_tree.heading("window", text="対象ウィンドウ")
        self.profile_tree.heading("output", text="保存先")
        self.profile_tree.column("#0", width=150)
        self.profile_tree.column("command", width=180)
        self.profile_tree.column("window", width=180)
        self.profile_tree.column("output", width=260)
        self.profile_tree.grid(row=1, column=0, sticky="nsew", pady=(4, 10))

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="w", pady=(0, 14))
        self.capture_button = ttk.Button(
            buttons,
            text="起動して撮影",
            command=self.start_capture,
        )
        self.capture_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="保存先を開く", command=self.open_output).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(buttons, text="一覧更新", command=self.refresh_profiles).grid(row=0, column=2)

        ttk.Label(self, text="実行ログ").grid(row=3, column=0, sticky="w")
        log_frame = ttk.Frame(self)
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(4, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def refresh_profiles(self) -> None:
        selected = self._selected_name()
        self.profile_tree.delete(*self.profile_tree.get_children())
        try:
            profiles = self.store.load_auto_capture_profiles()
        except SettingsError as exc:
            messagebox.showerror("設定エラー", str(exc))
            return
        for name, settings in profiles.items():
            self.profile_tree.insert(
                "",
                "end",
                iid=name,
                text=name,
                values=(
                    settings.command,
                    settings.window_title,
                    str(settings.output_path),
                ),
            )
        if selected and self.profile_tree.exists(selected):
            self.profile_tree.selection_set(selected)

    def _selected_name(self) -> str | None:
        selection = self.profile_tree.selection()
        return selection[0] if selection else None

    def _selected_settings(self) -> AutoCaptureSettings | None:
        name = self._selected_name()
        if name is None:
            messagebox.showwarning("設定選択", "自動撮影設定を選択してください。")
            return None
        try:
            return self.store.load_auto_capture_profiles().get(name)
        except SettingsError as exc:
            messagebox.showerror("設定エラー", str(exc))
            return None

    def start_capture(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showwarning("自動撮影", "自動撮影は既に実行中です。")
            return
        settings = self._selected_settings()
        if settings is None:
            return
        self.capture_button.configure(state="disabled")
        self._append_log(f"--- {settings.name} ---")
        self.worker = run_in_background(
            lambda: self._run_capture(settings),
            "auto-capture-worker",
        )

    def _run_capture(self, settings: AutoCaptureSettings) -> None:
        try:
            self.runner.run(settings, lambda message: self.messages.put(("log", message)))
        except (AutomationError, ValueError, OSError) as exc:
            self.messages.put(("error", str(exc)))
        finally:
            self.messages.put(("finished", ""))

    def _drain_messages(self) -> None:
        while True:
            try:
                kind, message = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(message)
            elif kind == "error":
                self._append_log(f"エラー: {message}")
                messagebox.showerror("自動撮影エラー", message)
            elif kind == "finished":
                self.capture_button.configure(state="normal")
        self.after(100, self._drain_messages)

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def open_output(self) -> None:
        settings = self._selected_settings()
        if settings is None:
            return
        directory = Path(settings.output_directory)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            os.startfile(directory)
        except OSError as exc:
            messagebox.showerror("保存先エラー", f"保存先を開けません: {exc}")


class AutoCaptureSettingsFrame(ttk.Frame):
    """CRUD operations for automatic capture profiles."""

    def __init__(
        self,
        master: ttk.Notebook,
        store: SettingsStore,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=18)
        self.store = store
        self.on_change = on_change
        self.test_messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build()
        self.refresh_profiles()
        self.after(100, self._drain_test_messages)

    def _build(self) -> None:
        ttk.Label(self, text="自動撮影設定").grid(row=0, column=0, sticky="w")
        self.tree = ttk.Treeview(
            self,
            columns=("command", "window", "match", "exit"),
            show="tree headings",
            height=14,
        )
        headings = {
            "#0": "設定名",
            "command": "実行コマンド",
            "window": "対象ウィンドウ",
            "match": "一致方法",
            "exit": "終了方法",
        }
        for column, heading in headings.items():
            self.tree.heading(column, text=heading)
        self.tree.column("#0", width=160)
        self.tree.column("command", width=220)
        self.tree.column("window", width=220)
        self.tree.column("match", width=90)
        self.tree.column("exit", width=180)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(4, 12))
        self.tree.bind("<Double-1>", lambda _event: self.edit_profile())

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="w")
        for column, (label, command) in enumerate(
            (
                ("新規登録", self.new_profile),
                ("編集", self.edit_profile),
                ("複製", self.duplicate_profile),
                ("削除", self.delete_profile),
                ("テスト起動", self.test_launch),
            )
        ):
            ttk.Button(buttons, text=label, command=command).grid(
                row=0,
                column=column,
                padx=(0, 8),
            )

    def refresh_profiles(self) -> None:
        self.tree.delete(*self.tree.get_children())
        try:
            profiles = self.store.load_auto_capture_profiles()
        except SettingsError as exc:
            messagebox.showerror("設定エラー", str(exc))
            return
        for name, settings in profiles.items():
            self.tree.insert(
                "",
                "end",
                iid=name,
                text=name,
                values=(
                    settings.command,
                    settings.window_title,
                    MATCH_MODE_LABELS[settings.title_match_mode],
                    EXIT_MODE_LABELS[settings.exit_mode],
                ),
            )

    def _selected(self) -> AutoCaptureSettings | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("設定選択", "設定を選択してください。")
            return None
        return self.store.load_auto_capture_profiles().get(selection[0])

    def new_profile(self) -> None:
        AutoCaptureSettingsDialog(self, self.store, None, self._changed)

    def edit_profile(self) -> None:
        settings = self._selected()
        if settings:
            AutoCaptureSettingsDialog(self, self.store, settings, self._changed)

    def duplicate_profile(self) -> None:
        settings = self._selected()
        if settings is None:
            return
        profiles = self.store.load_auto_capture_profiles()
        base = f"{settings.name} のコピー"
        name = base
        suffix = 2
        while name in profiles:
            name = f"{base} {suffix}"
            suffix += 1
        self.store.save_auto_capture_profile(replace(settings, name=name))
        self._changed()

    def delete_profile(self) -> None:
        settings = self._selected()
        if settings is None or not messagebox.askyesno(
            "設定削除", f"「{settings.name}」を削除しますか？"
        ):
            return
        self.store.delete_auto_capture_profile(settings.name)
        self._changed()

    def test_launch(self) -> None:
        settings = self._selected()
        if settings is None:
            return

        def launch() -> None:
            try:
                process = launch_application(settings)
            except AutomationError as exc:
                self.test_messages.put(("error", str(exc)))
                return
            self.test_messages.put(
                (
                    "success",
                    f"起動しました (PID: {process.pid})。\nアプリは自動終了しません。",
                )
            )

        run_in_background(launch, "test-launch-worker")

    def _drain_test_messages(self) -> None:
        while True:
            try:
                kind, message = self.test_messages.get_nowait()
            except queue.Empty:
                break
            if kind == "error":
                messagebox.showerror("テスト起動エラー", message)
            else:
                messagebox.showinfo("テスト起動", message)
        self.after(100, self._drain_test_messages)

    def _changed(self) -> None:
        self.refresh_profiles()
        self.on_change()


MATCH_MODE_LABELS = {
    TitleMatchMode.EXACT: "完全一致",
    TitleMatchMode.PARTIAL: "部分一致",
}
EXIT_MODE_LABELS = {
    ExitMode.GRACEFUL: "正常終了要求のみ",
    ExitMode.GRACEFUL_THEN_FORCE: "正常終了後に強制終了",
    ExitMode.LEAVE_RUNNING: "終了しない",
}


class AutoCaptureSettingsDialog(tk.Toplevel):
    """Editor dialog for one automatic capture profile."""

    def __init__(
        self,
        master: tk.Widget,
        store: SettingsStore,
        settings: AutoCaptureSettings | None,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.store = store
        self.original_name = settings.name if settings else None
        self.on_saved = on_saved
        self.title("自動撮影設定")
        self.resizable(True, True)
        self.transient(master.winfo_toplevel())
        # Keep the main window usable so this dialog itself can be selected and
        # captured from the manual capture tab.
        self.variables = self._make_variables(settings)
        self._build()
        self.minsize(700, 620)

    def _make_variables(self, settings: AutoCaptureSettings | None) -> dict[str, tk.Variable]:
        return {
            "name": tk.StringVar(value=settings.name if settings else ""),
            "command": tk.StringVar(value=settings.command if settings else ""),
            "working_directory": tk.StringVar(value=settings.working_directory if settings else ""),
            "arguments": tk.StringVar(value=settings.arguments if settings else ""),
            "window_title": tk.StringVar(value=settings.window_title if settings else ""),
            "title_match_mode": tk.StringVar(
                value=MATCH_MODE_LABELS[
                    settings.title_match_mode if settings else TitleMatchMode.EXACT
                ]
            ),
            "startup_timeout_seconds": tk.StringVar(
                value=str(settings.startup_timeout_seconds if settings else 30)
            ),
            "capture_delay_seconds": tk.StringVar(
                value=str(settings.capture_delay_seconds if settings else 1)
            ),
            "output_directory": tk.StringVar(value=settings.output_directory if settings else ""),
            "filename": tk.StringVar(value=settings.filename if settings else "screenshot.png"),
            "close_after_capture": tk.BooleanVar(
                value=settings.close_after_capture if settings else True
            ),
            "exit_mode": tk.StringVar(
                value=EXIT_MODE_LABELS[settings.exit_mode if settings else ExitMode.GRACEFUL]
            ),
            "shutdown_timeout_seconds": tk.StringVar(
                value=str(settings.shutdown_timeout_seconds if settings else 5)
            ),
            "add_sequence_number": tk.BooleanVar(
                value=settings.add_sequence_number if settings else False
            ),
            "date_suffix_mode": tk.StringVar(
                value=(
                    DATE_SUFFIX_DATETIME
                    if settings and settings.add_timestamp
                    else DATE_SUFFIX_DATE
                    if settings and settings.add_date
                    else DATE_SUFFIX_NONE
                )
            ),
        }

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        rows = [
            ("設定名", "name"),
            ("実行コマンド", "command"),
            ("作業ディレクトリ", "working_directory"),
            ("コマンドライン引数", "arguments"),
            ("対象ウィンドウタイトル", "window_title"),
            ("タイトル一致方法", "title_match_mode"),
            ("最大起動待機時間（秒）", "startup_timeout_seconds"),
            ("検出後の追加待機時間（秒）", "capture_delay_seconds"),
            ("保存先ディレクトリ", "output_directory"),
            ("保存ファイル名", "filename"),
            ("終了方法", "exit_mode"),
            ("終了待機時間（秒）", "shutdown_timeout_seconds"),
        ]
        for row, (label, key) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            if key == "title_match_mode":
                widget = ttk.Combobox(
                    frame,
                    textvariable=self.variables[key],
                    values=list(MATCH_MODE_LABELS.values()),
                    state="readonly",
                )
            elif key == "exit_mode":
                widget = ttk.Combobox(
                    frame,
                    textvariable=self.variables[key],
                    values=list(EXIT_MODE_LABELS.values()),
                    state="readonly",
                )
            else:
                widget = ttk.Entry(frame, textvariable=self.variables[key])
            widget.grid(row=row, column=1, sticky="ew", padx=(12, 8), pady=5)
            if key in {"command", "working_directory", "output_directory", "window_title"}:
                command = {
                    "command": self._choose_command,
                    "working_directory": lambda: self._choose_directory("working_directory"),
                    "output_directory": lambda: self._choose_directory("output_directory"),
                    "window_title": self._choose_window,
                }[key]
                text = "取得…" if key == "window_title" else "参照…"
                ttk.Button(frame, text=text, command=command).grid(
                    row=row, column=2, sticky="ew", pady=5
                )

        close_row = len(rows)
        ttk.Checkbutton(
            frame,
            text="ファイル名の先頭に連番を付ける（01_、02_…）",
            variable=self.variables["add_sequence_number"],
        ).grid(row=close_row, column=1, sticky="w", padx=(12, 0), pady=4)
        date_suffix_row = ttk.Frame(frame)
        date_suffix_row.grid(row=close_row + 1, column=1, sticky="w", padx=(12, 0), pady=4)
        ttk.Label(date_suffix_row, text="日付の付加:").grid(row=0, column=0, padx=(0, 8))
        for column, (label, value) in enumerate(
            (
                ("なし", DATE_SUFFIX_NONE),
                ("日付", DATE_SUFFIX_DATE),
                ("日時", DATE_SUFFIX_DATETIME),
            ),
            start=1,
        ):
            ttk.Radiobutton(
                date_suffix_row,
                text=label,
                value=value,
                variable=self.variables["date_suffix_mode"],
            ).grid(row=0, column=column, padx=(0, 8))
        ttk.Checkbutton(
            frame,
            text="撮影後にアプリを閉じる",
            variable=self.variables["close_after_capture"],
        ).grid(row=close_row + 2, column=1, sticky="w", padx=(12, 0), pady=4)
        buttons = ttk.Frame(frame)
        buttons.grid(row=close_row + 3, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="キャンセル", command=self.destroy).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(buttons, text="保存", command=self._save).grid(row=0, column=1)

    def _choose_command(self) -> None:
        selected = filedialog.askopenfilename(title="実行コマンドを選択")
        if selected:
            self.variables["command"].set(selected)

    def _choose_directory(self, key: str) -> None:
        selected = filedialog.askdirectory(title="ディレクトリを選択")
        if selected:
            self.variables[key].set(selected)

    def _choose_window(self) -> None:
        try:
            windows = list_windows()
        except WindowError as exc:
            messagebox.showerror("ウィンドウ取得エラー", str(exc), parent=self)
            return
        picker = tk.Toplevel(self)
        picker.title("対象ウィンドウを選択")
        picker.transient(self)
        picker.grab_set()
        tree = ttk.Treeview(
            picker,
            columns=("pid", "state"),
            show="tree headings",
            height=14,
        )
        tree.heading("#0", text="ウィンドウタイトル")
        tree.heading("pid", text="PID")
        tree.heading("state", text="状態")
        tree.column("#0", width=430)
        tree.column("pid", width=90)
        tree.column("state", width=90)
        for index, window in enumerate(windows):
            tree.insert(
                "",
                "end",
                iid=str(index),
                text=window.title,
                values=(window.process_id, window.state_label),
            )
        tree.pack(fill="both", expand=True, padx=12, pady=12)

        def select() -> None:
            selection = tree.selection()
            if selection:
                self.variables["window_title"].set(windows[int(selection[0])].title)
                picker.destroy()

        ttk.Button(picker, text="選択", command=select).pack(pady=(0, 12))
        tree.bind("<Double-1>", lambda _event: select())
        picker.minsize(650, 420)

    def _save(self) -> None:
        try:
            settings = AutoCaptureSettings(
                name=str(self.variables["name"].get()).strip(),
                command=str(self.variables["command"].get()).strip(),
                working_directory=str(self.variables["working_directory"].get()).strip(),
                arguments=str(self.variables["arguments"].get()).strip(),
                window_title=str(self.variables["window_title"].get()).strip(),
                title_match_mode=next(
                    mode
                    for mode, label in MATCH_MODE_LABELS.items()
                    if label == self.variables["title_match_mode"].get()
                ),
                startup_timeout_seconds=float(self.variables["startup_timeout_seconds"].get()),
                capture_delay_seconds=float(self.variables["capture_delay_seconds"].get()),
                output_directory=str(self.variables["output_directory"].get()).strip(),
                filename=str(self.variables["filename"].get()).strip(),
                close_after_capture=bool(self.variables["close_after_capture"].get()),
                exit_mode=next(
                    mode
                    for mode, label in EXIT_MODE_LABELS.items()
                    if label == self.variables["exit_mode"].get()
                ),
                shutdown_timeout_seconds=float(self.variables["shutdown_timeout_seconds"].get()),
                add_sequence_number=bool(self.variables["add_sequence_number"].get()),
                add_timestamp=(self.variables["date_suffix_mode"].get() == DATE_SUFFIX_DATETIME),
                add_date=self.variables["date_suffix_mode"].get() == DATE_SUFFIX_DATE,
            )
            validate_auto_capture_settings(settings)
            profiles = self.store.load_auto_capture_profiles()
            if (
                settings.name != self.original_name
                and settings.name in profiles
                and not messagebox.askyesno(
                    "設定上書き",
                    f"「{settings.name}」は既に存在します。上書きしますか？",
                    parent=self,
                )
            ):
                return
            if self.original_name and self.original_name != settings.name:
                self.store.delete_auto_capture_profile(self.original_name)
            self.store.save_auto_capture_profile(settings)
        except (ValueError, SettingsError, StopIteration) as exc:
            messagebox.showerror("設定エラー", str(exc), parent=self)
            return
        self.on_saved()
        self.destroy()


def run_gui(store: SettingsStore | None = None, profile: str = "default") -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    root.title("GUI Screenshot Tool")
    root.minsize(860, 620)
    settings_store = store or SettingsStore()
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    manual_frame = ScreenshotApp(notebook, settings_store, profile)
    automatic_frame = AutoCaptureFrame(notebook, settings_store)
    settings_frame = AutoCaptureSettingsFrame(
        notebook,
        settings_store,
        automatic_frame.refresh_profiles,
    )
    notebook.add(manual_frame, text="手動撮影")
    notebook.add(automatic_frame, text="自動撮影")
    notebook.add(settings_frame, text="設定管理")
    root.mainloop()
