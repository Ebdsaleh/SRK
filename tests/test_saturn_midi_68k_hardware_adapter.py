from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_hardware_adapter import (
    build_srk_saturn_midi_68k_hardware_adapter_contract,
    render_srk_saturn_midi_68k_hardware_adapter_header,
    render_srk_saturn_midi_68k_hardware_adapter_source,
)


class SaturnMidi68KHardwareAdapterTests(unittest.TestCase):
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[1]

    def test_contract_locks_physically_accepted_saturn_anchors(self):
        contract = build_srk_saturn_midi_68k_hardware_adapter_contract()
        self.assertEqual(contract.smpc_comreg_address, 0x2010001F)
        self.assertEqual(contract.smpc_sf_address, 0x20100063)
        self.assertEqual(contract.tvstat_address, 0x25F80004)
        self.assertEqual(contract.sound_ram_base, 0x25A00000)
        self.assertEqual(contract.sndon_command, 0x06)
        self.assertEqual(contract.sndoff_command, 0x07)
        self.assertEqual(contract.smpc_timeout, 1_000_000)

    def test_committed_adapter_matches_rendered_contract(self):
        root = self._repo_root() / "integrations" / "saturn" / "standalone"
        self.assertEqual(
            (root / "srk_saturn_midi_68k_hardware_adapter.h").read_text(encoding="utf-8"),
            render_srk_saturn_midi_68k_hardware_adapter_header(),
        )
        self.assertEqual(
            (root / "srk_saturn_midi_68k_hardware_adapter.c").read_text(encoding="utf-8"),
            render_srk_saturn_midi_68k_hardware_adapter_source(),
        )

    def test_adapter_reuses_accepted_type_b_flow_without_scsp_access(self):
        source = render_srk_saturn_midi_68k_hardware_adapter_source()
        self.assertIn("while(SRK_MIDI_ADAPTER_TVSTAT & 0x0008u)", source)
        self.assertIn("SRK_MIDI_ADAPTER_SMPC_SF = 0x01u;", source)
        self.assertIn("SRK_MIDI_ADAPTER_SMPC_COMREG = command;", source)
        self.assertLess(
            source.index("SRK_MIDI_ADAPTER_SMPC_SF = 0x01u;"),
            source.index("SRK_MIDI_ADAPTER_SMPC_COMREG = command;"),
        )
        self.assertIn("SRK_MIDI_ADAPTER_SMPC_SNDOFF", source)
        self.assertIn("SRK_MIDI_ADAPTER_SMPC_SNDON", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x25B00400", source)

    def test_preload_verification_reads_metadata_tones_and_every_queue_record(self):
        source = render_srk_saturn_midi_68k_hardware_adapter_source()
        self.assertIn("srk_saturn_midi_preload_is_ready()", source)
        for name in (
            "SRK_MIDI_MB_WRITE_SEQUENCE",
            "SRK_MIDI_MB_READ_SEQUENCE",
            "SRK_MIDI_MB_WRITE_INDEX",
            "SRK_MIDI_MB_READ_INDEX",
            "SRK_MIDI_MB_LAST_ERROR",
            "SRK_MIDI_TONE_BANK_ADDRESS",
            "SRK_MIDI_QUEUE_ADDRESS",
            "SRK_MIDI_EVENT_COUNT",
        ):
            self.assertIn(name, source)
        self.assertIn("event->time_us >> 16", source)
        self.assertIn("event->opcode << 8", source)
        self.assertIn("event->data0 << 8", source)

    def test_adapter_only_exposes_ops_and_never_calls_runtime_protocol(self):
        source = render_srk_saturn_midi_68k_hardware_adapter_source()
        header = render_srk_saturn_midi_68k_hardware_adapter_header()
        self.assertIn("SRK_SATURN_MIDI_68K_RUNTIME_OPS", source)
        self.assertIn("srk_saturn_midi_68k_hardware_adapter_ops", header)
        self.assertIn("srk_saturn_midi_68k_install_while_stopped", source)
        self.assertIn("srk_saturn_midi_preload_publish", source)
        self.assertNotIn("srk_saturn_midi_68k_protocol_begin(", source)
        self.assertNotIn("srk_saturn_midi_68k_protocol_poll(", source)


if __name__ == "__main__":
    unittest.main()
