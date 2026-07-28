"""Load and save per-user application settings."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gui_screenshot_tool.models import AppSettings

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
        if not self.path.exists():
            return {}
        try:
            raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
            apps = raw.get("apps", {})
            if not isinstance(apps, dict):
                raise ValueError("'apps' must be an object")
            return {
                name: AppSettings(
                    window_title=value["window_title"],
                    output_directory=value["output_directory"],
                    filename=value["filename"],
                )
                for name, value in apps.items()
                if isinstance(name, str) and isinstance(value, dict)
            }
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SettingsError(f"設定ファイルを読み込めません: {self.path}") from exc

    def get(self, profile: str = "default") -> AppSettings | None:
        return self.load_all().get(profile)

    def save(self, settings: AppSettings, profile: str = "default") -> None:
        apps = self.load_all()
        apps[profile] = settings
        data = {"apps": {name: asdict(value) for name, value in apps.items()}}
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
