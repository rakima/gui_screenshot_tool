"""Tkinter user interface."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from gui_screenshot_tool.capture import CaptureError, enable_dpi_awareness
from gui_screenshot_tool.config import SettingsError, SettingsStore
from gui_screenshot_tool.models import AppSettings, WindowInfo
from gui_screenshot_tool.service import capture_selected, validate_settings
from gui_screenshot_tool.windows import WindowError, list_windows


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
        self.status_var = tk.StringVar(value="ウィンドウ一覧を読み込んでいます…")
        self._build()
        self._load_settings()
        # EnumWindows only reports this application after Tk has mapped the root
        # window. Delaying the initial refresh also makes this tool selectable as
        # a README screenshot target.
        self.master.after(100, self.refresh_windows)

    def _build(self) -> None:
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
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
            row=5, column=0, sticky="ew", pady=(4, 18)
        )

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, sticky="e")
        ttk.Button(buttons, text="設定保存", command=self.save_settings).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(
            buttons,
            text="スクリーンショット撮影",
            command=self.capture,
            style="Accent.TButton",
        ).grid(row=0, column=1)
        ttk.Separator(self).grid(row=7, column=0, sticky="ew", pady=(18, 10))
        ttk.Label(self, textvariable=self.status_var).grid(row=8, column=0, sticky="w")

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


def run_gui(store: SettingsStore | None = None, profile: str = "default") -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    root.title("GUI Screenshot Tool")
    root.minsize(620, 330)
    ScreenshotApp(root, store or SettingsStore(), profile)
    root.mainloop()
