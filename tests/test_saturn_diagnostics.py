"""Tests for the standalone Saturn diagnostic-core contracts."""

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.diagnostics import (
    DIAGNOSTIC_MENU,
    FLIGHT_RECORDER_CAPACITY,
    FLIGHT_RECORD_SIZE,
    DiagnosticScreen,
    FlightRecord,
    FlightRecorder,
    InputState,
    NormalizedButton,
)


ROOT = Path(__file__).resolve().parents[1]
C_ROOT = ROOT / "integrations" / "saturn" / "diagnostics"


class SaturnDiagnosticsTests(unittest.TestCase):
    def test_menu_is_stable_and_title_neutral(self):
        self.assertEqual(len(DIAGNOSTIC_MENU), 8)
        self.assertEqual(DIAGNOSTIC_MENU[0], (DiagnosticScreen.INPUT_TEST, "Controller / Input Test"))
        self.assertEqual(DIAGNOSTIC_MENU[-1], (DiagnosticScreen.SYSTEM_INFORMATION, "System Information"))
        for _screen, label in DIAGNOSTIC_MENU:
            self.assertNotIn("Darius", label)
            self.assertNotIn("Soul Hackers", label)

    def test_normalized_input_tracks_edges_combinations_and_hold_duration(self):
        state = InputState()
        state.update(NormalizedButton.NONE, 0)

        state.update(NormalizedButton.L, 1_000)
        self.assertEqual(state.pressed, NormalizedButton.L)
        self.assertEqual(state.released, NormalizedButton.NONE)
        self.assertEqual(state.held_for_us(NormalizedButton.L), 0)

        state.update(NormalizedButton.L | NormalizedButton.R, 2_000)
        self.assertEqual(state.pressed, NormalizedButton.R)
        self.assertTrue(state.combination_active(NormalizedButton.L | NormalizedButton.R))

        state.update(NormalizedButton.L | NormalizedButton.R, 1_002_000)
        self.assertEqual(state.pressed, NormalizedButton.NONE)
        self.assertEqual(state.held_for_us(NormalizedButton.L), 1_001_000)
        self.assertEqual(state.held_for_us(NormalizedButton.R), 1_000_000)

        state.update(NormalizedButton.L, 1_102_000)
        self.assertEqual(state.released, NormalizedButton.R)
        self.assertFalse(state.combination_active(NormalizedButton.L | NormalizedButton.R))
        self.assertEqual(state.held_for_us(NormalizedButton.R), 1_100_000)

    def test_flight_record_is_exactly_32_bytes_and_round_trips(self):
        record = FlightRecord(
            timestamp_us=123456,
            frame=77,
            raw_pad=0xA55A,
            normalized_pad=int(NormalizedButton.L | NormalizedButton.R),
            pressed=int(NormalizedButton.L),
            released=int(NormalizedButton.A),
            held=int(NormalizedButton.L | NormalizedButton.R),
            diagnostic_id=int(DiagnosticScreen.INPUT_TEST),
            vbr=0x06000000,
            value0=0x11223344,
            value1=0x55667788,
        )
        packed = record.pack()
        self.assertEqual(FLIGHT_RECORD_SIZE, 32)
        self.assertEqual(len(packed), 32)
        self.assertEqual(FlightRecord.unpack(packed), record)

    def test_flight_recorder_is_a_30_second_60hz_rolling_ring(self):
        self.assertEqual(FLIGHT_RECORDER_CAPACITY, 1800)

        recorder = FlightRecorder(capacity=3)
        recorder.arm()
        for frame in range(5):
            recorder.append(
                FlightRecord(
                    timestamp_us=frame * 16_667,
                    frame=frame,
                    raw_pad=0,
                    normalized_pad=0,
                    pressed=0,
                    released=0,
                    held=0,
                    diagnostic_id=int(DiagnosticScreen.INPUT_TEST),
                    vbr=0,
                )
            )

        self.assertEqual([record.frame for record in recorder.records()], [2, 3, 4])
        recorder.freeze()
        recorder.append(
            FlightRecord(
                timestamp_us=999,
                frame=99,
                raw_pad=0,
                normalized_pad=0,
                pressed=0,
                released=0,
                held=0,
                diagnostic_id=0,
                vbr=0,
            )
        )
        self.assertEqual([record.frame for record in recorder.records()], [2, 3, 4])

    def test_c_core_uses_host_boundary_instead_of_known_r9_assumptions(self):
        files = (
            C_ROOT / "srk_diag_host.h",
            C_ROOT / "srk_diag_input.h",
            C_ROOT / "srk_diag_input.c",
            C_ROOT / "srk_diag_menu.h",
            C_ROOT / "srk_diag_menu.c",
            C_ROOT / "srk_diag_flight_recorder.h",
            C_ROOT / "srk_diag_flight_recorder.c",
        )
        for path in files:
            self.assertTrue(path.is_file(), path)

        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotIn("0x06020232", combined)
        self.assertNotIn("SS_TIMER", combined)
        self.assertNotIn("write_file(", combined)
        self.assertIn("raw_state", combined)
        self.assertIn("SRK_DIAG_BUTTON_L", combined)
        self.assertIn("SRK_DIAG_BUTTON_R", combined)

        menu_c = (C_ROOT / "srk_diag_menu.c").read_text(encoding="utf-8")
        for _screen, label in DIAGNOSTIC_MENU:
            self.assertIn(label, menu_c)


if __name__ == "__main__":
    unittest.main()
