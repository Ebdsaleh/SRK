"""Tests for SRK-specific workspace locations composed over Salix paths."""

from pathlib import Path
import unittest

from rikai_kotoba.application.paths import (
    default_output_directory,
    default_saroo_dump_directory,
    default_saturn_image_directory,
    workspace_directory,
)


class _FakePaths:
    def __init__(self, *, home: Path, application_directory: Path, portable=False, environ=None):
        self.home = home
        self.application_directory = application_directory
        self.environ = dict(environ or {})
        self._portable = bool(portable)

    def portable_mode(self):
        return self._portable


class SRKWorkspacePathTests(unittest.TestCase):
    def test_normal_install_uses_home_workspace_not_repository(self):
        paths = _FakePaths(
            home=Path("/home/researcher"),
            application_directory=Path("/opt/srk"),
        )
        self.assertEqual(
            workspace_directory(paths),
            Path("/home/researcher/SRK-Workspace"),
        )
        self.assertEqual(
            default_output_directory(paths),
            Path("/home/researcher/SRK-Workspace/Output"),
        )
        self.assertEqual(
            default_saturn_image_directory(paths),
            Path("/home/researcher/SRK-Workspace/Images/Saturn"),
        )
        self.assertEqual(
            default_saroo_dump_directory(paths),
            Path("/home/researcher/SRK-Workspace/Dumps/SAROO"),
        )

    def test_environment_override_selects_workspace_root(self):
        override = Path.cwd() / "synthetic-srk-workspace"
        paths = _FakePaths(
            home=Path("/unused"),
            application_directory=Path("/unused/app"),
            environ={"SRK_WORKSPACE_DIR": str(override)},
        )
        self.assertEqual(workspace_directory(paths), override.resolve())
        self.assertEqual(default_output_directory(paths), override.resolve() / "Output")

    def test_portable_mode_keeps_workspace_beside_application(self):
        paths = _FakePaths(
            home=Path("/home/researcher"),
            application_directory=Path("/portable/SRK"),
            portable=True,
        )
        self.assertEqual(
            workspace_directory(paths),
            Path("/portable/SRK/workspace"),
        )


if __name__ == "__main__":
    unittest.main()
