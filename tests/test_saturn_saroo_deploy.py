"""Tests for guarded deployment of standalone Saturn CUE/BIN images to SAROO."""

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.formats.saturn.mode1_image import write_single_track_mode1_bin_cue
from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN,
    SarooStandaloneImageDeploymentError,
    apply_saroo_standalone_image_deployment,
    plan_saroo_standalone_image_deployment,
)
from rikai_kotoba.tools.saturn_saroo_deploy import main as deploy_main


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _card(root: Path) -> Path:
    card = root / "CARD"
    saroo = card / "SAROO"
    iso = saroo / "ISO"
    iso.mkdir(parents=True)
    (iso / "TEST").mkdir()
    (saroo / "update").mkdir()
    (saroo / "ssfirm.bin").write_bytes(b"firmware")
    (saroo / "mcuapp.bin").write_bytes(b"mcu")
    (saroo / "saroocfg.txt").write_text("cfg\n", encoding="ascii")
    existing = iso / "Existing Game"
    existing.mkdir()
    (existing / "keep.bin").write_bytes(b"keep-me")
    return card


def _project(root: Path) -> Path:
    project = root / "PROJECT"
    build = project / "build"
    deploy = build / "SRK-Diagnostics"
    deploy.mkdir(parents=True)
    iso = build / "srk_diag.iso"
    iso.write_bytes(bytes(range(256)) * 16)  # 4096 bytes = two logical sectors.
    raw = deploy / "SRK-Diagnostics.bin"
    cue = deploy / "SRK-Diagnostics.cue"
    mode1 = write_single_track_mode1_bin_cue(iso, raw, cue)

    artifacts = []
    for path in (raw, cue):
        artifacts.append(
            {
                "path": path.relative_to(project).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha(path),
            }
        )
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "orchestration": "python-native",
        "artifacts": artifacts,
        "deployable": {
            "format": "cue-bin-mode1-2352",
            "bin": raw.relative_to(project).as_posix(),
            "cue": cue.relative_to(project).as_posix(),
            "sector_count": mode1.sector_count,
            "user_bytes": mode1.user_bytes,
            "raw_bytes": mode1.raw_bytes,
            "verified_against_iso": True,
        },
    }
    (project / "SRK_STANDALONE_BUILD.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return project


class SaturnSarooDeployTests(unittest.TestCase):
    def test_plan_is_read_only_and_revalidates_mode1_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)
            before = (card / "SAROO" / "ISO" / "Existing Game" / "keep.bin").read_bytes()

            plan = plan_saroo_standalone_image_deployment(card, project)

            self.assertEqual(plan.sector_count, 2)
            self.assertEqual(plan.raw_bytes, 4704)
            self.assertIsNone(plan.category_directory)
            self.assertFalse(plan.destination_directory.exists())
            self.assertEqual(
                (card / "SAROO" / "ISO" / "Existing Game" / "keep.bin").read_bytes(),
                before,
            )

    def test_apply_requires_exact_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)

            with self.assertRaises(SarooStandaloneImageDeploymentError):
                apply_saroo_standalone_image_deployment(
                    card,
                    project,
                    confirmation="yes",
                )
            self.assertFalse((card / "SAROO" / "ISO" / "SRK-Diagnostics").exists())

    def test_apply_copies_only_new_verified_game_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)
            existing = card / "SAROO" / "ISO" / "Existing Game" / "keep.bin"
            before = existing.read_bytes()

            result = apply_saroo_standalone_image_deployment(
                card,
                project,
                confirmation=CONFIRMATION_TOKEN,
            )

            destination = card / "SAROO" / "ISO" / "SRK-Diagnostics"
            # On Windows, tempfile may expose the same directory through an 8.3
            # short-path alias (for example DEVELO~1.ERI) while Path.resolve()
            # inside the deployment code returns the long form.  Compare the
            # resolved existing files rather than their lexical spellings.
            self.assertEqual(
                result.destination_bin.resolve(),
                (destination / "SRK-Diagnostics.bin").resolve(),
            )
            self.assertEqual(
                result.destination_cue.resolve(),
                (destination / "SRK-Diagnostics.cue").resolve(),
            )
            self.assertEqual(_sha(result.destination_bin), result.plan.bin_sha256)
            self.assertEqual(_sha(result.destination_cue), result.plan.cue_sha256)
            self.assertEqual(existing.read_bytes(), before)
            self.assertFalse((card / "SAROO" / "ISO" / ".SRK-Diagnostics.srk-pending").exists())

    def test_existing_category_can_be_selected_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)

            plan = plan_saroo_standalone_image_deployment(
                card,
                project,
                category="test",
            )

            self.assertIsNotNone(plan.category_directory)
            self.assertEqual(plan.category_directory.name, "TEST")
            self.assertEqual(
                plan.destination_directory,
                plan.category_directory / "SRK-Diagnostics",
            )
            self.assertFalse(plan.destination_directory.exists())

    def test_missing_category_is_rejected_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)
            missing = card / "SAROO" / "ISO" / "MISSING"

            with self.assertRaises(SarooStandaloneImageDeploymentError):
                plan_saroo_standalone_image_deployment(
                    card,
                    project,
                    category="MISSING",
                )

            self.assertFalse(missing.exists())
            self.assertFalse((card / "SAROO" / "ISO" / "SRK-Diagnostics").exists())

    def test_existing_destination_is_never_merged_or_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)
            destination = card / "SAROO" / "ISO" / "SRK-Diagnostics"
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_text("preserve", encoding="ascii")

            with self.assertRaises(SarooStandaloneImageDeploymentError):
                plan_saroo_standalone_image_deployment(card, project)
            self.assertEqual(marker.read_text(encoding="ascii"), "preserve")

    def test_tampered_deployable_bin_is_rejected_before_card_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            project = _project(root)
            raw = project / "build" / "SRK-Diagnostics" / "SRK-Diagnostics.bin"
            data = bytearray(raw.read_bytes())
            data[100] ^= 0x01
            raw.write_bytes(data)

            status = deploy_main(
                [
                    "--card-root", str(card),
                    "--project", str(project),
                ]
            )

            self.assertEqual(status, 2)
            self.assertFalse((card / "SAROO" / "ISO" / "SRK-Diagnostics").exists())


if __name__ == "__main__":
    unittest.main()
