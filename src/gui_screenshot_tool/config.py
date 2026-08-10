"""Load and save per-user application settings."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gui_screenshot_tool.models import (
    AppSettings,
    AutoCaptureSettings,
    ExitMode,
    TitleMatchMode,
)

APP_DIRECTORY_NAME = "gui_screenshot_tool"
SETTINGS_FILENAME = "settings.json"


class SettingsError(RuntimeError):
    """Raised when settings cannot be loaded or saved."""


def settings_path() -> Path:
    """Return the current user's settings path."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SettingsError("環境変数 APPDATA が設定されていません。")
    return Path(appdata) / APP_DIRECTORY_NAME / SETTINGS_FILENAME


class SettingsStore:
    """JSON-backed collection of capture profiles."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else settings_path()

    def load_all(self) -> dict[str, AppSettings]:
        raw = self._load_document()
        try:
            apps = raw.get("apps", {})
            if not isinstance(apps, dict):
                raise ValueError("'apps' must be an object")
            return {
                name: AppSettings(
                    window_title=value["window_title"],
                    output_directory=value["output_directory"],
                    filename=value["filename"],
                    add_sequence_number=bool(value.get("add_sequence_number", False)),
                    add_timestamp=bool(value.get("add_timestamp", False)),
                    add_date=bool(value.get("add_date", False)),
                )
                for name, value in apps.items()
                if isinstance(name, str) and isinstance(value, dict)
            }
        except (ValueError, KeyError, TypeError) as exc:
            raise SettingsError(f"設定ファイルを読み込めません: {self.path}") from exc

    def get(self, profile: str = "default") -> AppSettings | None:
        return self.load_all().get(profile)

    def save(self, settings: AppSettings, profile: str = "default") -> None:
        data = self._load_document()
        apps = data.setdefault("apps", {})
        if not isinstance(apps, dict):
            raise SettingsError(f"設定ファイルを読み込めません: {self.path}")
        apps[profile] = asdict(settings)
        self._save_document(data)

    def load_auto_capture_profiles(self) -> dict[str, AutoCaptureSettings]:
        """Load all registered automatic capture profiles."""
        raw = self._load_document()
        try:
            profiles = raw.get("auto_capture_profiles", {})
            if not isinstance(profiles, dict):
                raise ValueError("'auto_capture_profiles' must be an object")
            return {
                name: AutoCaptureSettings(
                    name=name,
                    command=value["command"],
                    working_directory=value["working_directory"],
                    arguments=value.get("arguments", ""),
                    window_title=value["window_title"],
                    title_match_mode=TitleMatchMode(
                        value.get("title_match_mode", TitleMatchMode.EXACT)
                    ),
                    startup_timeout_seconds=float(value["startup_timeout_seconds"]),
                    capture_delay_seconds=float(value["capture_delay_seconds"]),
                    output_directory=value["output_directory"],
                    filename=value["filename"],
                    close_after_capture=bool(value.get("close_after_capture", True)),
                    exit_mode=ExitMode(value.get("exit_mode", ExitMode.GRACEFUL)),
                    shutdown_timeout_seconds=float(value.get("shutdown_timeout_seconds", 5.0)),
                    add_sequence_number=bool(value.get("add_sequence_number", False)),
                    add_timestamp=bool(value.get("add_timestamp", False)),
                    add_date=bool(value.get("add_date", False)),
                )
                for name, value in profiles.items()
                if isinstance(name, str) and isinstance(value, dict)
            }
        except (ValueError, KeyError, TypeError) as exc:
            raise SettingsError(f"自動撮影設定を読み込めません: {self.path}") from exc

    def save_auto_capture_profile(self, settings: AutoCaptureSettings) -> None:
        data = self._load_document()
        profiles = data.setdefault("auto_capture_profiles", {})
        if not isinstance(profiles, dict):
            raise SettingsError(f"設定ファイルを読み込めません: {self.path}")
        profiles[settings.name] = asdict(settings)
        self._save_document(data)

    def delete_auto_capture_profile(self, name: str) -> None:
        data = self._load_document()
        profiles = data.get("auto_capture_profiles", {})
        if isinstance(profiles, dict):
            profiles.pop(name, None)
        self._save_document(data)

    def _load_document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("root must be an object")
            return raw
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise SettingsError(f"設定ファイルを読み込めません: {self.path}") from exc

    def _save_document(self, data: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            raise SettingsError(f"設定ファイルを保存できません: {self.path}") from exc
