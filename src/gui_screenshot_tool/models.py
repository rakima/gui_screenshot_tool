"""Shared domain models."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """A top-level Windows window."""

    handle: int
    title: str
    visible: bool
    minimized: bool
    process_id: int = 0

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
    add_sequence_number: bool = False
    add_timestamp: bool = False

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory) / self.filename


class TitleMatchMode(StrEnum):
    """Supported window-title matching strategies."""

    EXACT = "exact"
    PARTIAL = "partial"


class ExitMode(StrEnum):
    """How an automatically launched application is closed."""

    GRACEFUL = "graceful"
    GRACEFUL_THEN_FORCE = "graceful_then_force"
    LEAVE_RUNNING = "leave_running"


@dataclass(frozen=True, slots=True)
class AutoCaptureSettings:
    """Persisted settings for one launch-and-capture workflow."""

    name: str
    command: str
    working_directory: str
    arguments: str
    window_title: str
    title_match_mode: TitleMatchMode
    startup_timeout_seconds: float
    capture_delay_seconds: float
    output_directory: str
    filename: str
    close_after_capture: bool
    exit_mode: ExitMode
    shutdown_timeout_seconds: float = 5.0
    add_sequence_number: bool = False
    add_timestamp: bool = False

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory) / self.filename
