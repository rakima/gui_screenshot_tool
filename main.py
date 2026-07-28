"""Repository-local entry point."""

import sys
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SOURCE_DIRECTORY))

from gui_screenshot_tool.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
