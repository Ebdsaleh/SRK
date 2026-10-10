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
        self.assertIn("SRK_DIAG_AUDIO_TONE_MIXED_PAIR", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_PAN_LEFT", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_PAN_CENTER", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_PAN_RIGHT", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_TONE", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_SHAPED_PCM", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_PACKAGED_PCM", audio_h)

        for button in (
            "A", "B", "C", "LEFT", "UP", "RIGHT", "X", "Y", "Z", "L", "R"
        ):
            self.assertIn(f"pressed_buttons & SRK_DIAG_BUTTON_{button}", audio_c)

        self.assertIn("AUDIO / SCSP TEST", app_c)
        self.assertIn("A Play/Stop   C Mute/Unmute", app_c)
        self.assertIn("LEFT/UP/RIGHT Select L/Both/R", app_c)
        self.assertIn("X/Y/Z Tone Low/Mid/High", app_c)
        self.assertIn("L/R Volume   DOWN+A Stereo", app_c)
        self.assertIn("host->present_audio_tone", app_c)
        self.assertIn("host->stop_audio", app_c)
        self.assertIn("host->read_audio_status", app_c)

    def test_audio_screen_exposes_modes_sources_and_both_slot_registers(self):
        app_c = (DIAG / "srk_diag_app.c").read_text(encoding="utf-8")

        self.assertIn("Stages 1-6: deterministic PCM proofs", app_c)
        self.assertIn("srk_diag_audio_mode_label", app_c)
        self.assertIn("srk_diag_audio_source_label(&app->audio)", app_c)
        self.assertIn('return "SWEEP"', app_c)
        self.assertIn('return "MIXED"', app_c)
        self.assertIn('return "SHAPED"', app_c)
        self.assertIn('return "STEREO"', app_c)
        self.assertIn('return "SINGLE"', app_c)

        for label in (
            "S0 Src:", "S1 Src:", "S0 LEA:", "S1 LEA:", "S0 Pit:",
            "S1 Pit:", "S0 Mix:", "S1 Mix:", "S0 Ctl:", "S1 Ctl:",
        ):
            self.assertIn(label, app_c)

        self.assertIn("status.slot_source", app_c)
        self.assertIn("status.slot_loop_end", app_c)
        self.assertIn("status.slot1_source", app_c)
        self.assertIn("status.slot1_loop_end", app_c)
        self.assertIn("status.slot1_pitch", app_c)
        self.assertIn("status.slot1_mixer", app_c)
        self.assertIn("status.slot1_control", app_c)
        self.assertIn("DOWN+B Sweep  DOWN+C Shaped", app_c)
        self.assertIn("DOWN+Z Mixed pair", app_c)

    def test_stage2_stereo_pair_preserves_single_slot_mode_and_isolates_sources(self):
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")
        host_h = (STANDALONE / "srk_saturn_host.h").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_AUDIO_TONE_COUNT 5", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE_STEREO_PAIR = 3", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_TONE mono_tone", audio_h)
        self.assertIn("int stereo_pair", audio_h)
        self.assertIn('"STEREO"', audio_c)
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
        self.assertIn("SRK_AUDIO_CONTROL_KYONEX", backend)

    def test_stage2_down_a_is_explicit_stereo_both_play_chord(self):
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        self.assertIn("stereo_both_play", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_DOWN", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_A", audio_c)
        self.assertIn("srk_diag_audio_enter_stereo_pair(state);", audio_c)
        self.assertIn("state->playing = 1;", audio_c)

    def test_stage3_sweep_reuses_reviewed_tones_and_volume_levels(self):
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_AUDIO_SWEEP_STEP_COUNT 48", audio_h)
        self.assertIn("SRK_DIAG_AUDIO_SWEEP_FRAMES_PER_STEP 15", audio_h)
        self.assertIn("unsigned int sweep_frame", audio_h)
        self.assertIn("int sweep_active", audio_h)
        self.assertIn("sweep_toggle", audio_c)
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
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_C", audio_c)
        self.assertIn("srk_diag_audio_enter_sample_mode(state)", audio_c)
        self.assertIn("srk_diag_audio_leave_sample_mode(state)", audio_c)
        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_SHAPED_PCM", audio_c)
        self.assertIn('"SHAPED PCM"', audio_c)

        self.assertIn("unsigned int audio_waveform_id", saturn_host_h)
        self.assertIn("SRK_AUDIO_STAGE4_SAMPLE_ADDRESS 0x00002400u", backend)
        self.assertIn("SRK_AUDIO_STAGE4_SAMPLE_LOOP_END 256u", backend)
        self.assertIn("SRK_AUDIO_STAGE4_SHAPE_LEVEL_COUNT 16u", backend)
        self.assertIn("SRK_AUDIO_STAGE4_SAMPLES_PER_LEVEL 16u", backend)
        self.assertIn("srk_saturn_audio_install_stage4_sample()", backend)
        self.assertIn("srk_saturn_audio_set_slot_source", backend)
        self.assertIn("srk_saturn_audio_retarget_sources", backend)
        self.assertIn("srk_saturn_audio_apply_key_mask(0u)", backend)
        self.assertIn("state->audio_playing_mask = 0u", backend)

    def test_stage5_mixed_pair_uses_independent_sources_on_two_slots(self):
        host_h = (DIAG / "srk_diag_host.h").read_text(encoding="utf-8")
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")
        saturn_host_h = (STANDALONE / "srk_saturn_host.h").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_AUDIO_TONE_MIXED_PAIR = 4", audio_h)
        self.assertIn('"MIXED"', audio_c)
        self.assertIn("mixed_pair_toggle", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_Z", audio_c)
        self.assertIn("srk_diag_audio_enter_mixed_pair(state)", audio_c)
        self.assertIn("srk_diag_audio_leave_pair(state)", audio_c)
        self.assertIn('return "TONE+PCM"', audio_c)

        self.assertIn("unsigned int audio_right_waveform_id", saturn_host_h)
        self.assertIn("SRK_AUDIO_STAGE5_MIXED_TONE_ID 4u", backend)
        self.assertIn("desired_left_waveform", backend)
        self.assertIn("desired_right_waveform", backend)
        self.assertIn("SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;", backend)
        self.assertIn("SRK_AUDIO_STAGE4_WAVEFORM_SHAPED_PCM_ID;", backend)
        self.assertIn("left[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_MID", backend)
        self.assertIn("right[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_MID", backend)
        self.assertIn("srk_saturn_audio_retarget_sources", backend)

        self.assertIn("srk_u16 slot_source", host_h)
        self.assertIn("srk_u16 slot_loop_end", host_h)
        self.assertIn("srk_u16 slot1_source", host_h)
        self.assertIn("srk_u16 slot1_loop_end", host_h)
        self.assertIn("status->slot_source = left[SRK_AUDIO_SLOT_SA_LOW]", backend)
        self.assertIn("status->slot1_source = right[SRK_AUDIO_SLOT_SA_LOW]", backend)

    def test_stage6_packaged_pcm_uses_gfs_then_existing_single_slot_scsp_path(self):
        audio_h = (DIAG / "srk_diag_audio.h").read_text(encoding="utf-8")
        audio_c = (DIAG / "srk_diag_audio.c").read_text(encoding="utf-8")
        backend = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")
        runtime_h = (STANDALONE / "srk_saturn_packaged_pcm.h").read_text(encoding="utf-8")
        runtime_c = (STANDALONE / "srk_saturn_packaged_pcm.c").read_text(encoding="utf-8")
        host_h = (STANDALONE / "srk_saturn_host.h").read_text(encoding="utf-8")

        self.assertIn("SRK_DIAG_AUDIO_WAVEFORM_PACKAGED_PCM = 2", audio_h)
        self.assertIn("int packaged_mode", audio_h)
        self.assertIn("packaged_toggle", audio_c)
        self.assertIn("pressed_buttons & SRK_DIAG_BUTTON_Y", audio_c)
        self.assertIn("srk_diag_audio_enter_packaged_mode", audio_c)
        self.assertIn("srk_diag_audio_leave_packaged_mode", audio_c)
        self.assertIn('return "DISC PCM"', audio_c)

        self.assertIn("SRK_SATURN_PACKAGED_PCM_FILE_BYTES 1040u", runtime_h)
        self.assertIn("SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT 512u", runtime_h)
        self.assertIn('#include "SEGA_GFS.H"', runtime_c)
        self.assertIn("GFS_DIR_NAME", runtime_c)
        self.assertIn("GFS_DIRTBL_DIRNAME", runtime_c)
        self.assertIn("GFS_Init", runtime_c)
        self.assertIn('GFS_NameToId((Sint8 *)"SRKPCM.BIN")', runtime_c)
        self.assertIn("GFS_GetFileSize", runtime_c)
        self.assertIn("GFS_Load", runtime_c)
        self.assertIn("GFS_Close", runtime_c)
        self.assertIn("result != (Sint32)SRK_SATURN_PACKAGED_PCM_FILE_BYTES", runtime_c)
        self.assertIn("SRK_PCM_MAGIC_0 'S'", runtime_c)
        self.assertIn("SRK_PCM_VERSION 1u", runtime_c)
        self.assertIn("SRK_PCM_ENCODING_PCM16_BE 1u", runtime_c)
        self.assertIn("SRK_PCM_CHANNELS_MONO 1u", runtime_c)

        self.assertIn("audio_packaged_attempted", host_h)
        self.assertIn("audio_packaged_ready", host_h)
        self.assertIn("SRK_SATURN_PACKAGED_PCM audio_packaged_pcm", host_h)
        self.assertIn("SRK_AUDIO_STAGE6_SAMPLE_ADDRESS 0x00002800u", backend)
        self.assertIn("SRK_AUDIO_STAGE6_WAVEFORM_PACKAGED_PCM_ID 2u", backend)
        self.assertIn("srk_saturn_audio_prepare_packaged", backend)
        self.assertIn("srk_saturn_packaged_pcm_load", backend)
        self.assertIn("srk_saturn_audio_install_stage6_sample", backend)
        self.assertIn("SRK_AUDIO_STAGE6_SAMPLE_LOOP_END", backend)
        self.assertIn("pcm->samples[pcm->loop_start]", backend)

    def test_scsp_backend_uses_reviewed_sound_cpu_and_slot_contract(self):
        audio_c = (STANDALONE / "srk_saturn_audio.c").read_text(encoding="utf-8")

        self.assertIn("0x25A00000", audio_c)
        self.assertIn("0x25B00000", audio_c)
        self.assertIn("0x25B00400", audio_c)
        self.assertIn("0x2010001F", audio_c)
        self.assertIn("0x20100063", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_SNDON  0x06u", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_SNDOFF 0x07u", audio_c)

        self.assertIn("volatile srk_u16 *)0x25A00000", audio_c)
        self.assertIn("volatile srk_u16 *)0x25B00000", audio_c)
        self.assertIn("volatile srk_u16 *)0x25B00400", audio_c)
        self.assertNotIn("volatile srk_u8 *)0x25A00000", audio_c)
        self.assertNotIn("volatile srk_u8 *)0x25B00000", audio_c)
        self.assertNotIn("volatile srk_u8 *)0x25B00400", audio_c)

        self.assertIn("SRK_AUDIO_SOUND_CPU_STACK 0x0007FFF0ul", audio_c)
        self.assertIn("SRK_AUDIO_SOUND_CPU_PC    0x00000400ul", audio_c)
        self.assertIn("SRK_AUDIO_VECTOR_COUNT    256u", audio_c)
        self.assertIn("= 0x60FEu", audio_c)

        self.assertIn("SRK_AUDIO_CONTROL_NORMAL_LOOP 0x0020u", audio_c)
        self.assertIn("SRK_AUDIO_SOUND_DIRECT 0x0100u", audio_c)
        self.assertIn("SRK_AUDIO_CONTROL_KYONEX 0x1000u", audio_c)
        self.assertIn("SRK_AUDIO_CONTROL_KYONB  0x0800u", audio_c)
        self.assertIn("SRK_AUDIO_LOOP_END        100u", audio_c)
        self.assertIn("SRK_AUDIO_SAMPLE_POSITIVE 0x2000u", audio_c)
        self.assertIn("SRK_AUDIO_SAMPLE_NEGATIVE 0xE000u", audio_c)

        self.assertIn("SRK_AUDIO_PAN_HARD_LEFT  0x1Fu", audio_c)
        self.assertIn("SRK_AUDIO_PAN_CENTER     0x00u", audio_c)
        self.assertIn("SRK_AUDIO_PAN_HARD_RIGHT 0x0Fu", audio_c)
        self.assertIn("SRK_AUDIO_PITCH_LOW  0x7800u", audio_c)
        self.assertIn("SRK_AUDIO_PITCH_MID  0x0000u", audio_c)
        self.assertIn("SRK_AUDIO_PITCH_HIGH 0x0800u", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_SF = 0x01u", audio_c)
        self.assertIn("SRK_AUDIO_SMPC_COMREG = command", audio_c)
        self.assertIn("while(SRK_AUDIO_TVSTAT & 0x0008u)", audio_c)

    def test_generated_project_and_builder_carry_all_audio_layers(self):
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
        self.assertIn('"srk_saturn_packaged_pcm.c"', project_py)
        self.assertIn('"srk_saturn_packaged_pcm.h"', project_py)
        self.assertIn('"srk_diag_audio.c"', build_py)
        self.assertIn('"srk_saturn_audio.c"', build_py)
        self.assertIn('"srk_saturn_packaged_pcm.c"', build_py)
        self.assertIn("stage6b_gfs", build_py)
        self.assertIn("srk_saturn_audio_bind(&srk_host, &srk_host_state)", main_c)


if __name__ == "__main__":
    unittest.main()