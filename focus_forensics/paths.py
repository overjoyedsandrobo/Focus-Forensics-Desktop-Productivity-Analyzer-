from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "FocusForensics"


def data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data)
    else:
        root = Path.home() / ".focus_forensics"
    path = root / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_file(filename: str) -> Path:
    return data_dir() / filename
