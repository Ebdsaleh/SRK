"""SRK composition over the reusable Salix runtime-path policy."""

from __future__ import annotations

import sys
from pathlib import Path

from salix.runtime.paths import RuntimePathSpec, RuntimePaths


_PATH_SPEC = RuntimePathSpec(
    app_name="SRK",
    portable_flag_name="portable.flag",
    portable_env="SRK_PORTABLE",
    state_dir_env="SRK_STATE_DIR",
    download_dir_env="SRK_WORKSPACE_DIR",
    portable_state_directory="data",
    portable_download_directory="workspace",
)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_directory() -> Path:
    return Path(__file__).resolve().parents[3]


def application_directory() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_directory()


def runtime_paths() -> RuntimePaths:
    return RuntimePaths(
        _PATH_SPEC,
        bundle_directory=bundle_directory(),
        application_directory=application_directory(),
    )


def state_directory() -> Path:
    return runtime_paths().state_directory()


def resource_path(relative_path: str | Path) -> Path:
    return runtime_paths().resource_path(relative_path)
