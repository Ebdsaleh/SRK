"""Regression tests for the fresh inert Saturn MIDI full-build gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_full_build_gate import (
    SaturnMidiFullBuildGateError,
    prepare_inert_midi_full_build_gate,
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


class SaturnMidiFullBuildGateTests(unittest.TestCase):
    def test_derives_fresh_gate_without_mutating_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            before = _snapshot(baseline)
            output = root / "gate"

            result = prepare_inert_midi_full_build_gate(baseline, output)

            self.assertEqual(_snapshot(baseline), before)
            self.assertEqual(result.baseline_root, baseline.resolve())
            self.assertEqual(result.output_root, output.resolve())
            self.assertFalse((output / _REPORT).exists())

            runtime = (output / _RUNTIME).read_text(encoding="utf-8")
            bridge_source = (output / "src/srk_saturn_midi_generated.c").read_text(
                encoding="utf-8"
            )
            bridge_header = (output / "src/srk_saturn_midi_generated.h").read_text(
                encoding="utf-8"
            )
            self.assertIn("SRK MIDI INERT FULL-BUILD GATE", runtime)
            self.assertIn(bridge_source, runtime)
            self.assertIn("SRK_MIDI_EVENT_COUNT", bridge_header)
            self.assertNotIn("volatile", bridge_source)
            self.assertNotIn("volatile", bridge_header)

            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            self.assertFalse(manifest["midi_bridge_gate"]["behaviorally_active"])
            self.assertFalse(manifest["policy"]["midi_bridge_active"])
            self.assertFalse(manifest["policy"]["midi_sound_ram_writes"])
            self.assertFalse(manifest["policy"]["midi_scsp_mmio"])
            self.assertFalse(manifest["policy"]["midi_mc68ec000_execution"])

            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            for relative in (
                _RUNTIME,
                "src/srk_saturn_midi_generated.c",
                "src/srk_saturn_midi_generated.h",
            ):
                path = output / relative
                self.assertIn(relative, inventory)
                self.assertEqual(inventory[relative]["size"], path.stat().st_size)
                self.assertEqual(inventory[relative]["sha256"], sha256(path.read_bytes()).hexdigest())

    def test_refuses_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            output = root / "gate"
            output.mkdir()

            with self.assertRaisesRegex(SaturnMidiFullBuildGateError, "already exists"):
                prepare_inert_midi_full_build_gate(baseline, output)

    def test_rejects_tampered_baseline_generated_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            (baseline / _RUNTIME).write_bytes(b"tampered\n")

            with self.assertRaisesRegex(SaturnMidiFullBuildGateError, "size mismatch|hash mismatch"):
                prepare_inert_midi_full_build_gate(baseline, root / "gate")

    def test_rejects_unsuccessful_baseline_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root, successful=False)

            with self.assertRaisesRegex(SaturnMidiFullBuildGateError, "was not successful"):
                prepare_inert_midi_full_build_gate(baseline, root / "gate")


if __name__ == "__main__":
    unittest.main()
