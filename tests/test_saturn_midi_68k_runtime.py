"""Regression tests for the silent Saturn MIDI 68K runtime orchestration contract."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_runtime import (
    SATURN_MIDI_ACK_READ_INDEX,
    SATURN_MIDI_ACK_READ_SEQUENCE,
    SATURN_MIDI_SMPC_COMREG_ADDRESS,
    SATURN_MIDI_SMPC_SF_ADDRESS,
    SATURN_MIDI_SMPC_SNDON,
    SATURN_MIDI_SMPC_SNDOFF,
    SATURN_MIDI_TVSTAT_ADDRESS,
    SaturnMidi68KProtocolSnapshot,
    SaturnMidi68KRuntimeStatus,
    classify_srk_saturn_midi_68k_protocol_snapshot,
    render_srk_saturn_midi_68k_runtime_header,
    render_srk_saturn_midi_68k_runtime_source,
)
from rikai_kotoba.hardware.saturn.midi_mailbox import SATURN_MIDI_MAILBOX_FLAG_READY


_ROOT = Path(__file__).resolve().parents[1]
_STANDALONE = _ROOT / "integrations" / "saturn" / "standalone"
_RUNTIME_H = _STANDALONE / "srk_saturn_midi_68k_runtime.h"
_RUNTIME_C = _STANDALONE / "srk_saturn_midi_68k_runtime.c"


class SaturnMidi68KRuntimeTests(unittest.TestCase):
    def test_accepted_smpc_anchors_and_status_values_are_locked(self):
        self.assertEqual(SATURN_MIDI_SMPC_COMREG_ADDRESS, 0x2010001F)
        self.assertEqual(SATURN_MIDI_SMPC_SF_ADDRESS, 0x20100063)
        self.assertEqual(SATURN_MIDI_TVSTAT_ADDRESS, 0x25F80004)
        self.assertEqual(SATURN_MIDI_SMPC_SNDON, 0x06)
        self.assertEqual(SATURN_MIDI_SMPC_SNDOFF, 0x07)
        self.assertEqual(SATURN_MIDI_ACK_READ_SEQUENCE, 1)
        self.assertEqual(SATURN_MIDI_ACK_READ_INDEX, 1)
        self.assertEqual(int(SaturnMidi68KRuntimeStatus.ACKNOWLEDGED), 6)
        self.assertEqual(int(SaturnMidi68KRuntimeStatus.CONSUMER_ERROR), 7)

    def test_snapshot_classifies_only_exact_acknowledgement_as_acknowledged(self):
        snapshot = SaturnMidi68KProtocolSnapshot(
            flags=SATURN_MIDI_MAILBOX_FLAG_READY,
            read_sequence=1,
            read_index=1,
            last_error=0,
        )
        self.assertEqual(
            classify_srk_saturn_midi_68k_protocol_snapshot(snapshot),
            SaturnMidi68KRuntimeStatus.ACKNOWLEDGED,
        )

    def test_snapshot_distinguishes_running_from_consumer_error(self):
        running = SaturnMidi68KProtocolSnapshot(
            flags=SATURN_MIDI_MAILBOX_FLAG_READY,
            read_sequence=0,
            read_index=0,
            last_error=0,
        )
        failed = SaturnMidi68KProtocolSnapshot(
            flags=SATURN_MIDI_MAILBOX_FLAG_READY,
            read_sequence=0,
            read_index=0,
            last_error=5,
        )
        self.assertEqual(
            classify_srk_saturn_midi_68k_protocol_snapshot(running),
            SaturnMidi68KRuntimeStatus.RUNNING,
        )
        self.assertEqual(
            classify_srk_saturn_midi_68k_protocol_snapshot(failed),
            SaturnMidi68KRuntimeStatus.CONSUMER_ERROR,
        )

    def test_committed_c_matches_renderer_and_orders_runtime_operations(self):
        header = _RUNTIME_H.read_text(encoding="utf-8")
        source = _RUNTIME_C.read_text(encoding="utf-8")
        self.assertEqual(header, render_srk_saturn_midi_68k_runtime_header())
        self.assertEqual(source, render_srk_saturn_midi_68k_runtime_source())

        begin = source[source.index("unsigned int srk_saturn_midi_68k_protocol_begin") :]
        positions = [
            begin.index("ops->stop_sound_cpu()"),
            begin.index("ops->install_program()"),
            begin.index("ops->publish_preload()"),
            begin.index("ops->verify_preload()"),
            begin.index("ops->start_sound_cpu()"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("0x2010001F", source)
        self.assertNotIn("0x20100063", source)
        self.assertNotIn("0x25A00000", source)
        self.assertNotIn("0x25B00000", source)

    def test_runtime_layer_is_not_called_by_existing_standalone_sources(self):
        needle = "srk_saturn_midi_68k_protocol_begin"
        offenders = []
        for path in _STANDALONE.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".c", ".h"}:
                continue
            if path in {_RUNTIME_C, _RUNTIME_H}:
                continue
            if needle in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
