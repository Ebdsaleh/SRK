"""Cross-platform locations for SRK's local runtime state."""

from __future__ import annotations

import os
from pathlib import Path


def state_directory() -> Path:
    """Return a per-user state directory without depending on the repo path."""

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "SRK"
        return Path.home() / "AppData" / "Local" / "SRK"

    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "srk"
    return Path.home() / ".local" / "state" / "srk"
