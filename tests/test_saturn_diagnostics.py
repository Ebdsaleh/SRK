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
STANDALONE_ROOT = ROOT / "integrations" / "saturn" / "standalone"


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
            C_ROOT / "srk_diag_vdp1.h",
            C_ROOT / "srk_diag_vdp1.c",
            C_ROOT / "srk_diag_video.h",
            C_ROOT / "srk_diag_video.c",
            C_ROOT / "srk_diag_app.h",
            C_ROOT / "srk_diag_app.c",
        )
        for path in files:
            self.assertTrue(path.is_file(), path)

        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotIn("0x06020232", combined)
        self.assertNotIn("0x25C00000", combined)
        self.assertNotIn("0x25D00000", combined)
        self.assertNotIn("0x25E00000", combined)
        self.assertNotIn("0x25F80000", combined)
        self.assertNotIn("0x25F800E0", combined)
        self.assertNotIn("0x25F800F0", combined)
        self.assertNotIn("SS_TIMER", combined)
        self.assertNotIn("write_file(", combined)
        self.assertIn("raw_state", combined)
        self.assertIn("SRK_DIAG_BUTTON_L", combined)
        self.assertIn("SRK_DIAG_BUTTON_R", combined)
        self.assertIn("draw_video_pattern", combined)
        self.assertIn("present_vdp1_quad", combined)
        self.assertIn("present_vdp1_scene", combined)
        self.assertIn("read_vdp1_status", combined)

        menu_c = (C_ROOT / "srk_diag_menu.c").read_text(encoding="utf-8")
        for _screen, label in DIAGNOSTIC_MENU:
            self.assertIn(label, menu_c)

    def test_c_shell_exposes_input_and_flight_recorder_debug_behaviour(self):
        app_c = (C_ROOT / "srk_diag_app.c").read_text(encoding="utf-8")
        app_h = (C_ROOT / "srk_diag_app.h").read_text(encoding="utf-8")
        vdp1_h = (C_ROOT / "srk_diag_vdp1.h").read_text(encoding="utf-8")
        vdp1_c = (C_ROOT / "srk_diag_vdp1.c").read_text(encoding="utf-8")
        host_c = (STANDALONE_ROOT / "srk_saturn_host.c").read_text(encoding="utf-8")
        startup_s = (STANDALONE_ROOT / "srk_saturn_startup.S").read_text(encoding="utf-8")

        self.assertIn("CONTROLLER / INPUT TEST", app_c)
        self.assertIn("Raw:", app_c)
        self.assertIn("Normalized:", app_c)
        self.assertIn("PRESSED", app_c)
        self.assertIn("HELD", app_c)
        self.assertIn("RELEASED", app_c)
        self.assertIn("L+R combination:", app_c)
        self.assertIn("L+R+START Return to diagnostics menu", app_c)
        self.assertIn("SRK_DIAG_INPUT_EXIT_MASK", app_c)
        self.assertIn("APPLICATION FLIGHT RECORDER", app_c)
        self.assertIn("A Arm/reset rolling recorder", app_c)
        self.assertIn("C Freeze current 30-second window", app_c)
        self.assertIn("START Return to diagnostics menu", app_c)

        self.assertIn("VDP1 / 3D TEST", app_c)
        self.assertIn("Stage 3: interactive cube dynamics", app_c)
        self.assertIn("D-PAD Pitch/Yaw   L/R Roll", app_c)
        self.assertIn("A/B Speed   C Freeze/Run", app_c)
        self.assertIn("X Pastel  Y Neon  Z Original", app_c)
        self.assertIn("Visible faces:", app_c)
        self.assertIn("State:", app_c)
        self.assertIn("Palette:", app_c)
        self.assertIn("Speed:", app_c)
        self.assertIn("VX:", app_c)
        self.assertIn("VY:", app_c)
        self.assertIn("VZ:", app_c)
        self.assertIn("EDSR:", app_c)
        self.assertIn("LOPR:", app_c)
        self.assertIn("COPR:", app_c)
        self.assertIn("MODR:", app_c)
        self.assertIn("srk_diag_vdp1_control", app_c)
        self.assertIn("app->input.current", app_c)
        self.assertIn("app->input.pressed", app_c)
        self.assertIn("host->present_vdp1_scene", app_c)
        self.assertIn("host->present_vdp1_quad", app_c)
        self.assertIn("srk_diag_vdp1_advance", app_c)
        self.assertIn("host->hide_vdp1", app_c)
        self.assertIn("host->read_vdp1_status", app_c)

        self.assertIn("SRK_DIAG_VDP1_CUBE_VERTEX_COUNT 8", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_CUBE_FACE_COUNT   6", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_MOTION_SHIFT      8", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_SPEED_ONE         256", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_SPEED_MAX         1024", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_VELOCITY_MAX      1536", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_PALETTE_ORIGINAL", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_PALETTE_PASTEL", vdp1_h)
        self.assertIn("SRK_DIAG_VDP1_PALETTE_NEON", vdp1_h)
        self.assertIn("velocity_x", vdp1_h)
        self.assertIn("velocity_y", vdp1_h)
        self.assertIn("velocity_z", vdp1_h)
        self.assertIn("speed_q8", vdp1_h)
        self.assertIn("frozen", vdp1_h)

        self.assertIn("srk_diag_vdp1_sine_quarter", vdp1_c)
        self.assertIn("static void srk_diag_vdp1_rotate_vertex", vdp1_c)
        self.assertIn("SRK_DIAG_VDP1_VECTOR3 *result", vdp1_c)
        self.assertIn("static void srk_diag_vdp1_project", vdp1_c)
        self.assertIn("SRK_DIAG_VDP1_POINT *point", vdp1_c)
        self.assertIn("srk_diag_vdp1_face_normal_z", vdp1_c)
        self.assertIn("srk_diag_vdp1_face_depth", vdp1_c)
        self.assertIn("srk_diag_vdp1_palettes", vdp1_c)
        self.assertIn("{ 255, 160, 144 }", vdp1_c)
        self.assertIn("{ 255,  32,   0 }", vdp1_c)
        self.assertIn("SRK_DIAG_VDP1_ACCEL_Q8", vdp1_c)
        self.assertIn("SRK_DIAG_VDP1_SPEED_STEP_Q8", vdp1_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_C", vdp1_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_X", vdp1_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_Y", vdp1_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_Z", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_UP", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_DOWN", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_LEFT", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_RIGHT", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_L", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_R", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_A", vdp1_c)
        self.assertIn("held_buttons & SRK_DIAG_BUTTON_B", vdp1_c)
        self.assertIn("state->velocity_x = SRK_DIAG_VDP1_SPEED_ONE", vdp1_c)
        self.assertIn("state->velocity_y = SRK_DIAG_VDP1_SPEED_ONE", vdp1_c)
        self.assertIn("state->velocity_z = SRK_DIAG_VDP1_SPEED_ONE", vdp1_c)
        self.assertIn("state->speed_q8 = SRK_DIAG_VDP1_SPEED_ONE", vdp1_c)
        self.assertIn("if(state->frozen)\n        return;", vdp1_c)
        self.assertIn("if(!state->frozen)", vdp1_c)
        self.assertNotIn("transformed[i] = srk_diag_vdp1_rotate_vertex", vdp1_c)
        self.assertNotIn("quad->vertex[j] = srk_diag_vdp1_project", vdp1_c)
        self.assertNotIn("#include <math.h>", vdp1_c)

        self.assertIn("0x25C00000", host_c)
        self.assertIn("0x25D00000", host_c)
        self.assertIn("0x25F800E0", host_c)
        self.assertIn("0x25F800F0", host_c)
        self.assertIn("srk_saturn_present_vdp1_scene", host_c)
        self.assertIn("SRK_DIAG_VDP1_MAX_QUADS + 3u", host_c)
        self.assertIn("0x0009", host_c)
        self.assertIn("0x0004", host_c)
        self.assertIn("0x8000", host_c)
        self.assertIn("0x0020", host_c)
        self.assertIn("0x50DF", host_c)

        # Historical SH-ELF GCC may lower aggregate copies to external _memcpy
        # even in a freestanding -fno-builtin translation unit. The standalone
        # startup owns that ABI helper so the final image remains -nostdlib.
        self.assertIn(".global _memcpy", startup_s)
        self.assertIn("_memcpy:", startup_s)
        self.assertIn("mov.b   @r5+,r1", startup_s)
        self.assertIn("mov     r4,r0", startup_s)

        # The physical R4 test exposed full-screen flashing because the visible
        # bitmap was cleared every frame. Rendering now clears only on an
        # initial screen/transition and overwrites dynamic fields in place.
        self.assertIn("rendered_screen_valid", app_h)
        self.assertIn("full_render", app_c)
        self.assertIn("if(full_render && host->clear)", app_c)
        self.assertIn("srk_diag_draw_field", app_c)
        self.assertNotIn("if(host->clear)\n        host->clear(host->context);", app_c)

    def test_video_pattern_contract_is_title_neutral_and_host_rendered(self):
        video_h = (C_ROOT / "srk_diag_video.h").read_text(encoding="utf-8")
        video_c = (C_ROOT / "srk_diag_video.c").read_text(encoding="utf-8")
        app_c = (C_ROOT / "srk_diag_app.c").read_text(encoding="utf-8")
        host_c = (STANDALONE_ROOT / "srk_saturn_host.c").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_VIDEO_PATTERN_COUNT 10", video_h)
        for label in (
            "Solid Black",
            "Solid White",
            "Solid Red",
            "Solid Green",
            "Solid Blue",
            "RGB / Color Bars",
            "Grayscale / Brightness Ramp",
            "Checkerboard",
            "Fine Grid",
            "Overscan / Safe Area",
        ):
            self.assertIn(label, video_c)

        self.assertIn("SRK_DIAG_SCREEN_VIDEO_PATTERN_TEST", app_c)
        self.assertIn("LEFT/RIGHT Change pattern", app_c)
        self.assertIn("srk_diag_video_move", app_c)
        self.assertIn("host->draw_video_pattern", app_c)

        self.assertIn("SRK_VDP2_VRAM", host_c)
        self.assertIn("SRK_VDP2_CRAM", host_c)
        self.assertIn("srk_saturn_draw_color_bars", host_c)
        self.assertIn("srk_saturn_draw_grayscale", host_c)
        self.assertIn("srk_saturn_draw_checkerboard", host_c)
        self.assertIn("srk_saturn_draw_grid", host_c)
        self.assertIn("srk_saturn_draw_safe_area", host_c)
        self.assertIn("host->draw_video_pattern = srk_saturn_draw_video_pattern", host_c)


if __name__ == "__main__":
    unittest.main()
