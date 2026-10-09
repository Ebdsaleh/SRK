"""Regression contracts for Saturn Audio / SCSP diagnostics."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "integrations" / "saturn" / "diagnostics"
STANDALONE = ROOT / "integrations" / "saturn" / "standalone"


class SaturnAudioDiagnosticsTests(unittest.TestCase):
    def test_audio_core_is_title_neutral_and_controller_deterministic(self):
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        app_c = (DIAG / "srk_diag_app.c").read_text(encoding="utf-8")
        combined = audio_h + "\n" + audio_c + "\n" + app_c

        for address in (
            "0x25A00000",
            "0x25B00000",
            "0x25B00400",
            "0x2010001F",
            "0x20100063",
        ):
            self.assertNotIn(address, combined)

        self.assertIn("SRK_DIAG_AUDIO_DEFAULT_VOLUME 4", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_VOLUME_MAX 7", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE_LOW", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE_MID", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE_HIGH", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE_STEREO_PAIR", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_PAN_LEFT", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_PAN_CENTER", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_PAN_RIGHT", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_TONE", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_SHAPED_PCM", audio_h)

        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_A", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_B", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_C", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_LEFT", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_UP", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_RIGHT", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_X", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_Y", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_Z", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_L", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_R", audio_c)

        self.assertIn("AUDIO / SCSP TEST", app_c)
        self.assertIn("A Play/Stop   C Mute/Unmute", app_c)
        self.assertIn("LEFT/UP/RIGHT Pan L/C/R", app_c)
        self.assertIn("X/Y/Z Tone Low/Mid/High", app_c)
        self.assertIn("L/R Volume Down/Up", app_c)
        self.assertIn("host->present_audio_tone", app_c)
        self.assertIn("host->stop_audio", app_c)
        self.assertIn("host->read_audio_status", app_c)

    def test_stage2_stereo_pair_preserves_single_slot_mode_and_isolates_sources(self):
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")
        host_h = (STANDALONE / "srk_saturn_host.h").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_AUDIO_TONE_COUNT 4", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE_STEREO_PAIR = 3", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE mono_tone", audio_h)
        self.assertIn("int stereo_pair", audio_h)
        self.assertIn('"STEREO"', audio_c)
        self.assertIn("if(state->stereo_pair)", audio_c)
        self.assertIn("state->stereo_pair = 0;", audio_c)
        self.assertIn("state->stereo_pair = 1;", audio_c)
        self.assertIn("state->tone = SRK_DIAG_AUDIO_TONE_STEREO_PAIR", audio_c)
        self.assertIn("state->pan = SRK_DIAG_AUDIO_PAN_CENTER", audio_c)

        self.assertIn("unsigned int audio_playing_mask", host_h)
        self.assertIn("SRK_AUDIO_STAGE2_STEREO_TONE_ID 3u", backend)
        self.assertIn("SRK_AUDIO_STAGE2_LEFT_SLOT 0u", backend)
        self.assertIn("SRK_AUDIO_STAGE2_RIGHT_SLOT 1u", backend)
        self.assertIn("SRK_AUDIO_STAGE2_LEFT_MASK 0x01u", backend)
        self.assertIn("SRK_AUDIO_STAGE2_RIGHT_MASK 0x02u", backend)
        self.assertIn("srk_saturn_audio_configure_slot(SRK_AUDIO_STAGE2_LEFT_SLOT)", backend)
        self.assertIn("srk_saturn_audio_configure_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT)", backend)
        self.assertIn("left[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_LOW", backend)
        self.assertIn("right[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_HIGH", backend)
        self.assertIn("request->pan_id != 2u", backend)
        self.assertIn("request->pan_id != 0u", backend)
        self.assertIn("KYONEX executes the KYONB state for all slots at once", backend)

    def test_stage2_down_a_is_explicit_stereo_both_play_chord(self):
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")

        self.assertIn("stereo_both_play", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_DOWN", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_A", audio_c)
        self.assertIn("srk_diag_audio_enter_stereo_pair(state);", audio_c)
        self.assertIn("state->playing = 1;", audio_c)
        self.assertIn("UP therefore remains a selector, not a play command", audio_c)

    def test_stage3_sweep_reuses_reviewed_tones_and_volume_levels(self):
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_AUDIO_SWEEP_STEP_COUNT 48", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_SWEEP_FRAMES_PER_STEP 15", audio_h)
        self.assertIn("unsigned int sweep_frame", audio_h)
        self.assertIn("int sweep_active", audio_h)
        self.assertIn("sweep_toggle", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_DOWN", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_B", audio_c)
        self.assertIn("srk_diag_audio_enter_sweep(state)", audio_c)
        self.assertIn("srk_diag_audio_leave_sweep(state)", audio_c)
        self.assertIn("srk_diag_audio_advance_sweep(state)", audio_c)
        self.assertIn("state->tone = SRK_DIAG_AUDIO_TONE_LOW", audio_c)
        self.assertIn("state->tone = SRK_DIAG_AUDIO_TONE_MID", audio_c)
        self.assertIn("state->tone = SRK_DIAG_AUDIO_TONE_HIGH", audio_c)
        self.assertIn("state->volume = (srk_u8)level", audio_c)
        self.assertIn("state->volume = (srk_u8)(7u - level)", audio_c)
        self.assertIn("state->pan = SRK_DIAG_AUDIO_PAN_CENTER", audio_c)

        # Stage 3 intentionally adds no new SCSP pitch constants: it exercises
        # the already-reviewed LOW/MID/HIGH OCT encodings and DISDL levels.
        self.assertIn("SRK_AUDIO_PITCH_LOW  0x7800u", backend)
        self.assertIn("SRK_AUDIO_PITCH_MID  0x0000u", backend)
        self.assertIn("SRK_AUDIO_PITCH_HIGH 0x0800u", backend)
        self.assertNotIn("SRK_AUDIO_PITCH_SWEEP", backend)

    def test_stage4_shaped_pcm_switches_a_second_sound_ram_source_safely(self):
        host_h = (DIAG / "srk_diag_host.h").read_text(encoding="utf-8")
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")
        saturn_host_h = (STANDALONE / "srk_saturn_host.h").read_text(encoding="utf-8")

        self.assertIn("unsigned int waveform_id", host_h)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_SHAPED_PCM = 1", audio_h)
        self.assertIn("int sample_mode", audio_h)
        self.assertIn("sample_toggle", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_DOWN", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_C", audio_c)
        self.assertIn("srk_diag_audio_enter_sample_mode(state)", audio_c)
        self.assertIn("srk_diag_audio_leave_sample_mode(state)", audio_c)
        self.assertIn("request->waveform_id = state->sample_mode", audio_c)
        self.assertIn('"SHAPED PCM"', audio_c)

        self.assertIn("unsigned int audio_waveform_id", saturn_host_h)
        self.assertIn("SRK_AUDIO_STAGE4_SAMPLE_ADDRESS 0x00002400u", backend)
        self.assertIn("SRK_AUDIO_STAGE4_SAMPLE_LOOP_END 256u", backend)
        self.assertIn("SRK_AUDIO_STAGE4_SHAPE_LEVEL_COUNT 16u", backend)
        self.assertIn("SRK_AUDIO_STAGE4_SAMPLES_PER_LEVEL 16u", backend)
        self.assertIn("srk_saturn_audio_install_stage4_sample()", backend)
        self.assertIn("srk_saturn_audio_set_slot_source", backend)
        self.assertIn("desired_waveform != state->audio_waveform_id", backend)
        self.assertIn("srk_saturn_audio_apply_key_mask(0u)", backend)
        self.assertIn("state->audio_playing_mask = 0u", backend)

    def test_scsp_backend_uses_reviewed_sound_cpu_and_slot_contract(self):
        audio_c = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")

        # SH-2 cache-through sound block and SMPC command registers.
        self.assertIn("0x25A00000", audio_c)
        self.assertIn("0x25B00000", audio_c)
        self.assertIn("0x25B00400", audio_c)
        self.assertIn("0x2010001F", audio_c)
        self.assertIn("0x20100063", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_SNDON  0x06u", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_SNDOFF 0x07u", audio_c)

        # Main-side Sound RAM/SCSP access is word based, never byte based.
        self.assertIn("volatile srk_u16 *)0x25A00000", audio_c)
        self.assertIn("volatile srk_u16 *)0x25B00000", audio_c)
        self.assertIn("volatile srk_u16 *)0x25B00400", audio_c)
        self.assertNotIn("volatile srk_u8 *)0x25A00000", audio_c)
        self.assertNotIn("volatile srk_u8 *)0x25B00000", audio_c)
        self.assertNotIn("volatile srk_u8 *)0x25B00400", audio_c)

        # Technical Bulletin #51: bounded dummy 68000 remains alive after setup.
        self.assertIn("SRK_AUDIO_SOUND_CPU_STACK 0x0007FFF0ul", audio_c)
        self.assertIn("SRK_AUDIO_SOUND_CPU_PC    0x00000400ul", audio_c)
        self.assertIn("SRK_AUDIO_VECTOR_COUNT    256u", audio_c)
        self.assertIn("= 0x60FEu", audio_c)
        self.assertIn("do not leave Sound CPU OFF", audio_c)

        # Reviewed direct-PCM slot contract.
        self.assertIn("SRK_AUDIO_CONTROL_NORMAL_LOOP 0x0020u", audio_c)
        self.assertIn("SRK_AUDIO_SOUND_DIRECT 0x0100u", audio_c)
        self.assertIn("SRK_AUDIO_CONTROL_KYONEX 0x1000u", audio_c)
        self.assertIn("SRK_AUDIO_CONTROL_KYONB  0x0800u", audio_c)
        self.assertIn("SRK_AUDIO_LOOP_END        100u", audio_c)
        self.assertIn("SRK_AUDIO_SAMPLE_POSITIVE 0x2000u", audio_c)
        self.assertIn("SRK_AUDIO_SAMPLE_NEGATIVE 0xE000u", audio_c)

        # Sega DIPAN table: 1F hard-left, 00 center, 0F hard-right.
        self.assertIn("SRK_AUDIO_PAN_HARD_LEFT  0x1Fu", audio_c)
        self.assertIn("SRK_AUDIO_PAN_CENTER     0x00u", audio_c)
        self.assertIn("SRK_AUDIO_PAN_HARD_RIGHT 0x0Fu", audio_c)

        # OCT encodings: -1, 0, +1 with FNS=0.
        self.assertIn("SRK_AUDIO_PITCH_LOW  0x7800u", audio_c)
        self.assertIn("SRK_AUDIO_PITCH_MID  0x0000u", audio_c)
        self.assertIn("SRK_AUDIO_PITCH_HIGH 0x0800u", audio_c)

        # Type-B SMPC command issue and V-BLANK timing guard are explicit.
        self.assertIn("SRK_AUDIO_SMPC_SF = 0x01u", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_COMREG = command", audio_c)
        self.assertIn("while(SRK_AUDIO_TVSTAT & 0x0008u)", audio_c)

    def test_generated_project_and_builder_carry_both_audio_layers(self):
        project_py = (
            ROOT / "src" / "rikai_kotoba" / "hardware" / "saturn" / "standalone_project.py"
        ).read_text(encoding="utf-8")
        build_py = (
            ROOT / "src" / "rikai_kotoba" / "hardware" / "saturn" / "standalone_build.py"
        ).read_text(encoding="utf-8")
        main_c = (STANDALONE / "srk_saturn_main.c").read_text(encoding="utf-8")

        self.assertIn('"srk_diag_audio.c"', project_py)
        self.assertIn('"srk_diag_audio.h"', project_py)
        self.assertIn('"srk_saturn_audio.c"', project_py)
        self.assertIn('"srk_saturn_audio.h"', project_py)
        self.assertIn('"srk_diag_audio.c"', build_py)
        self.assertIn('"srk_saturn_audio.c"', build_py)
        self.assertIn("srk_saturn_audio_bind(&srk_host, &srk_host_state)", main_c)


if __name__ == "__main__":
    unittest.main()
