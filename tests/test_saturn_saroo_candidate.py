"""Tests for the composed one-command Saturn candidate workflow."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    SarooCardInventoryResult,
    SarooCardInventoryVerification,
)
from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN,
    SarooStandaloneImageDeploymentPlan,
    SarooStandaloneImageDeploymentResult,
)
from rikai_kotoba.hardware.saturn.saroo.standalone_workflow import (
    SaturnStandaloneSarooWorkflowError,
    run_saturn_standalone_saroo_workflow,
)
from rikai_kotoba.hardware.saturn.standalone_build import (
    SaturnStandaloneBuildResult,
)
from rikai_kotoba.hardware.saturn.standalone_project import (
    SaturnStandaloneProjectResult,
)
from rikai_kotoba.tools.saturn_saroo_candidate import build_parser, _resolved_arguments


def _project(root: Path) -> SaturnStandaloneProjectResult:
    return SaturnStandaloneProjectResult(
        output_root=root / "PROJECT",
        source_root=root / "PROJECT" / "src",
        build_script=root / "PROJECT" / "build.bat",
        ip_bin=root / "PROJECT" / "IP.BIN",
        manifest=root / "PROJECT" / "SRK_STANDALONE_PROJECT.json",
        gcc=root / "tools" / "sh-elf-gcc.exe",
        assembler=root / "tools" / "sh-elf-as.exe",
        iso_builder=root / "tools" / "mkisofs.exe",
    )


def _build(project: SaturnStandaloneProjectResult, *, successful: bool = True) -> SaturnStandaloneBuildResult:
    return SaturnStandaloneBuildResult(
        project_root=project.output_root,
        log_path=project.output_root / "SRK_STANDALONE_BUILD_LOG.txt",
        report_path=project.output_root / "SRK_STANDALONE_BUILD.json",
        commands=tuple(),
        artifacts=tuple(),
        successful=successful,
    )


def _plan(root: Path, project: SaturnStandaloneProjectResult) -> SarooStandaloneImageDeploymentPlan:
    card = root / "CARD"
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R11"
    return SarooStandaloneImageDeploymentPlan(
        card_root=card,
        project_root=project.output_root,
        iso_directory=card / "SAROO" / "ISO",
        category_directory=card / "SAROO" / "ISO" / "TEST",
        destination_directory=destination,
        source_bin=project.output_root / "build" / "SRK-Diagnostics" / "SRK-Diagnostics.bin",
        source_cue=project.output_root / "build" / "SRK-Diagnostics" / "SRK-Diagnostics.cue",
        source_iso=project.output_root / "build" / "srk_diag.iso",
        bin_size=150528,
        cue_size=81,
        bin_sha256="b" * 64,
        cue_sha256="c" * 64,
        sector_count=64,
        raw_bytes=150528,
    )


class SaturnSarooCandidateTests(unittest.TestCase):
    def test_read_only_run_stops_before_snapshot_or_card_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project(root)
            build = _build(project)
            plan = _plan(root, project)
            calls = []

            def prepare(*args, **kwargs):
                calls.append("prepare")
                return project

            def builder(*args, **kwargs):
                calls.append("build")
                return build

            def planner(*args, **kwargs):
                calls.append("plan")
                return plan

            def forbidden(*args, **kwargs):
                self.fail("read-only candidate unexpectedly reached a write-stage primitive")

            result = run_saturn_standalone_saroo_workflow(
                root / "SATURN",
                root / "template",
                root / "IP.BIN",
                project.output_root,
                plan.card_root,
                root / "guard.json",
                destination_name="SRK-Diagnostics-R11",
                category="TEST",
                _prepare=prepare,
                _build=builder,
                _plan=planner,
                _snapshot=forbidden,
                _apply=forbidden,
                _verify=forbidden,
            )

            self.assertEqual(calls, ["prepare", "build", "plan"])
            self.assertFalse(result.applied)
            self.assertFalse(result.card_verified)
            self.assertIsNone(result.guard)

    def test_invalid_apply_confirmation_fails_before_any_work(self):
        called = []

        def forbidden(*args, **kwargs):
            called.append(True)
            self.fail("invalid confirmation must fail before project preparation")

        with self.assertRaises(SaturnStandaloneSarooWorkflowError):
            run_saturn_standalone_saroo_workflow(
                "SATURN",
                "template",
                "IP.BIN",
                "PROJECT",
                "CARD",
                "guard.json",
                apply=True,
                confirmation="yes",
                _prepare=forbidden,
            )
        self.assertEqual(called, [])

    def test_apply_snapshots_once_and_requires_post_write_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project(root)
            build = _build(project)
            plan = _plan(root, project)
            manifest = root / "guard.json"
            calls = []
            observed_allowed = []

            guard = SarooCardInventoryResult(
                card_root=plan.card_root,
                manifest_path=manifest,
                file_count=10,
                directory_count=4,
                total_file_bytes=1000,
                hashed_file_count=8,
                manifest_sha256="a" * 64,
            )
            deployment = SarooStandaloneImageDeploymentResult(
                plan=plan,
                destination_bin=plan.destination_directory / plan.source_bin.name,
                destination_cue=plan.destination_directory / plan.source_cue.name,
                bin_sha256=plan.bin_sha256,
                cue_sha256=plan.cue_sha256,
            )
            verification = SarooCardInventoryVerification(
                card_root=plan.card_root,
                manifest_path=manifest,
                valid=True,
                differences=tuple(),
                file_count=12,
                directory_count=5,
                total_file_bytes=151609,
                hashed_file_count=10,
            )

            def prepare(*args, **kwargs):
                calls.append("prepare")
                return project

            def builder(*args, **kwargs):
                calls.append("build")
                return build

            def planner(*args, **kwargs):
                calls.append("plan")
                return plan

            def snapshot(*args, **kwargs):
                calls.append("snapshot")
                return guard

            def apply(*args, **kwargs):
                calls.append("apply")
                self.assertEqual(kwargs["confirmation"], CONFIRMATION_TOKEN)
                return deployment

            def verify(*args, **kwargs):
                calls.append("verify")
                observed_allowed.extend(kwargs["allowed_changed_paths"])
                return verification

            result = run_saturn_standalone_saroo_workflow(
                root / "SATURN",
                root / "template",
                root / "IP.BIN",
                project.output_root,
                plan.card_root,
                manifest,
                destination_name="SRK-Diagnostics-R11",
                category="TEST",
                apply=True,
                confirmation=CONFIRMATION_TOKEN,
                _prepare=prepare,
                _build=builder,
                _plan=planner,
                _snapshot=snapshot,
                _apply=apply,
                _verify=verify,
            )

            self.assertEqual(calls, ["prepare", "build", "plan", "snapshot", "apply", "verify"])
            self.assertTrue(result.applied)
            self.assertTrue(result.card_verified)
            self.assertEqual(
                observed_allowed,
                [
                    "SAROO/ISO/TEST/SRK-Diagnostics-R11",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R11/SRK-Diagnostics.bin",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R11/SRK-Diagnostics.cue",
                ],
            )

    def test_failed_build_never_reaches_card_planning_or_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project(root)
            failed_build = _build(project, successful=False)

            def forbidden(*args, **kwargs):
                self.fail("failed build must stop before card planning")

            with self.assertRaises(SaturnStandaloneSarooWorkflowError):
                run_saturn_standalone_saroo_workflow(
                    root / "SATURN",
                    root / "template",
                    root / "IP.BIN",
                    project.output_root,
                    root / "CARD",
                    root / "guard.json",
                    apply=True,
                    confirmation=CONFIRMATION_TOKEN,
                    _prepare=lambda *args, **kwargs: project,
                    _build=lambda *args, **kwargs: failed_build,
                    _plan=forbidden,
                    _snapshot=forbidden,
                    _apply=forbidden,
                    _verify=forbidden,
                )

    def test_revision_defaults_derive_fresh_project_destination_and_guard(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "--saturn-root", "C:/Saturn-Dev",
                "--workspace", "C:/SRK-Workspace",
                "--card-root", "D:/",
                "--revision", "r11",
                "--release-date", "20261009",
            ]
        )
        revision, date, template, ip_bin, output, name, guard = _resolved_arguments(args, parser)

        self.assertEqual(revision, "R11")
        self.assertEqual(date, "20261009")
        self.assertEqual(output, Path("C:/Saturn-Dev") / "SRK-Diagnostics-R1-R11")
        self.assertEqual(name, "SRK-Diagnostics-R11")
        self.assertEqual(
            guard,
            Path("C:/SRK-Workspace/Backups/SAROO/card_before_srk_diagnostics_r11_20261009.json"),
        )
        self.assertEqual(
            template,
            Path("C:/Saturn-Dev/SaturnOrbit-Inspect/payload/app/EXAMPLES/CharlesMacDonald/vdp1ex"),
        )
        self.assertEqual(
            ip_bin,
            Path("C:/Saturn-Dev/SaturnOrbit-Inspect/payload/app/COMMON/IP.BIN"),
        )


if __name__ == "__main__":
    unittest.main()
