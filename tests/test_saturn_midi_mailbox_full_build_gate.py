"""Regression tests for the inert Saturn MIDI mailbox full-build gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_mailbox_full_build_gate import (
    SaturnMidiMailboxFullBuildGateError,
    prepare_inert_midi_mailbox_full_build_gate,
)


_RUNTIME = "src/srk_saturn_runtime.c"
_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _baseline(root: Path, *, successful: bool = True) -> Path:
    baseline = root / "baseline"
    baseline.mkdir()
    files = {
        _RUNTIME: b"void *memset(void *dst, int value, unsigned long size) { return dst; }\n",
        "src/srk_saturn_main.c": b"int main(void) { return 0; }\n",
        "srk_saturn.ld": b"SECTIONS { .text 0x06004000 : { *(.text*) } }\n",
        "IP.BIN": b"IP-BIN-FIXTURE\n",
        "cd/SRKPCM.BIN": b"SRKP-FIXTURE\n",
        "build.bat": b"@echo off\r\n",
    }
    entries = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _sha(data),
            }
        )

    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
            "source_trees_read_only": True,
            "sd_writes": False,
        },
        "generated_files": entries,
    }
    manifest_path = baseline / _MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": successful,
        "project_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
    }
    (baseline / _REPORT).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return baseline


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class SaturnMidiMailboxFullBuildGateTests(unittest.TestCase):
    def test_derives_fresh_gate_with_bridge_and_uncalled_mailbox_producer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            before = _snapshot(baseline)
            output = root / "gate"

            result = prepare_inert_midi_mailbox_full_build_gate(baseline, output)

            self.assertEqual(_snapshot(baseline), before)
            self.assertEqual(result.baseline_root, baseline.resolve())
            self.assertEqual(result.output_root, output.resolve())
            self.assertFalse((output / _REPORT).exists())

            runtime = (output / _RUNTIME).read_text(encoding="utf-8")
            self.assertIn("SRK MIDI INERT FULL-BUILD GATE", runtime)
            self.assertIn("SRK MIDI MAILBOX INERT FULL-BUILD GATE", runtime)
            self.assertIn("srk_saturn_midi_events", runtime)
            self.assertIn("srk_saturn_midi_preload_publish", runtime)

            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            gate = manifest["midi_mailbox_full_build_gate"]
            self.assertTrue(gate["producer_linked"])
            self.assertFalse(gate["producer_called"])
            self.assertFalse(gate["behaviorally_active"])
            self.assertTrue(manifest["policy"]["midi_mailbox_producer_linked"])
            self.assertFalse(manifest["policy"]["midi_mailbox_producer_called"])
            self.assertFalse(manifest["policy"]["midi_sound_ram_writes"])
            self.assertFalse(manifest["policy"]["midi_scsp_mmio"])
            self.assertFalse(manifest["policy"]["midi_smpc_commands"])
            self.assertFalse(manifest["policy"]["midi_mc68ec000_execution"])

    def test_manifest_pins_mailbox_copies_and_modified_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "gate"
            prepare_inert_midi_mailbox_full_build_gate(_baseline(root), output)

            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            for relative in (
                _RUNTIME,
                "src/srk_saturn_midi_generated.c",
                "src/srk_saturn_midi_generated.h",
                "src/srk_saturn_midi_mailbox.c",
                "src/srk_saturn_midi_mailbox.h",
            ):
                path = output / relative
                self.assertTrue(path.is_file())
                self.assertIn(relative, inventory)
                self.assertEqual(inventory[relative]["size"], path.stat().st_size)
                self.assertEqual(
                    inventory[relative]["sha256"],
                    sha256(path.read_bytes()).hexdigest(),
                )

    def test_refuses_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            output = root / "gate"
            output.mkdir()

            with self.assertRaisesRegex(
                SaturnMidiMailboxFullBuildGateError,
                "already exists",
            ):
                prepare_inert_midi_mailbox_full_build_gate(baseline, output)

    def test_rejects_unsuccessful_or_tampered_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root, successful=False)
            with self.assertRaisesRegex(
                SaturnMidiMailboxFullBuildGateError,
                "was not successful",
            ):
                prepare_inert_midi_mailbox_full_build_gate(baseline, root / "gate-a")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            (baseline / _RUNTIME).write_bytes(b"tampered\n")
            with self.assertRaisesRegex(
                SaturnMidiMailboxFullBuildGateError,
                "size mismatch|hash mismatch",
            ):
                prepare_inert_midi_mailbox_full_build_gate(baseline, root / "gate-b")


if __name__ == "__main__":
    unittest.main()
