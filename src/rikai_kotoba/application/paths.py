"""SRK composition over the reusable Salix runtime-path policy."""

from __future__ import annotations

import os
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


def workspace_directory(paths: RuntimePaths | None = None) -> Path:
    """Return SRK's external research workspace root.

    Normal installations deliberately keep generated research artifacts outside
    the source repository under ``~/SRK-Workspace``. ``SRK_WORKSPACE_DIR`` can
    override that location. Portable mode keeps the workspace beside the
    application using the path declared by the reusable Salix path policy.
    """

    active = paths or runtime_paths()
    override = active.environ.get(_PATH_SPEC.download_dir_env)
    if override:
        return Path(os.path.abspath(os.path.expanduser(override)))
    if active.portable_mode():
        return active.application_directory / _PATH_SPEC.portable_download_directory
    return active.home / "SRK-Workspace"


def default_output_directory(paths: RuntimePaths | None = None) -> Path:
    return workspace_directory(paths) / "Output"


def default_saturn_image_directory(paths: RuntimePaths | None = None) -> Path:
    return workspace_directory(paths) / "Images" / "Saturn"


def default_saroo_dump_directory(paths: RuntimePaths | None = None) -> Path:
    return workspace_directory(paths) / "Dumps" / "SAROO"


def default_saroo_backup_directory(paths: RuntimePaths | None = None) -> Path:
    """Return the default off-card backup root for SAROO firmware evidence."""

    return workspace_directory(paths) / "Backups" / "SAROO"


def resource_path(relative_path: str | Path) -> Path:
    return runtime_paths().resource_path(relative_path)
