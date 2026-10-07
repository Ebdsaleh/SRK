"""Small resource-path helper for reusable Salix presentation adapters."""

from __future__ import annotations

from pathlib import Path


def resource_path(relative_path: str | Path) -> Path:
    """Resolve a documentation/media resource without depending on cwd.

    Absolute paths pass through unchanged. Relative paths are resolved from the
    installed source/package root; product-specific writable paths remain the
    responsibility of the application composition layer.
    """

    path = Path(relative_path).expanduser()
    if path.is_absolute():
        return path
    package_root = Path(__file__).resolve().parents[2]
    return package_root / path
