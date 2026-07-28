"""Shared domain models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """A top-level Windows window."""

    handle: int
    title: str
    visible: bool
    minimized: bool

    @property
    def state_label(self) -> str:
        if self.minimized:
            return "最小化"
        return "表示中" if self.visible else "非表示"

    @property
    def display_name(self) -> str:
        return f"{self.title}  [0x{self.handle:08X} / {self.state_label}]"


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Persisted capture settings for one application."""

    window_title: str
    output_directory: str
    filename: str

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory) / self.filename
