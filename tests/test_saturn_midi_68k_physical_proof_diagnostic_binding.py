from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STANDALONE = REPO_ROOT / "integrations" / "saturn" / "standalone"
MAIN = STANDALONE / "srk_saturn_main.c"


def _main_source() -> str:
    return MAIN.read_text(encoding="utf-8")


def test_diagnostic_binding_is_compile_time_guarded_and_disabled_by_default():
    source = _main_source()

    assert "#ifdef SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE" in source
    assert '#include "srk_saturn_midi_68k_physical_proof.h"' in source
    assert "#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE" not in source
    assert "srk_midi_68k_candidate_frame();" in source


def test_diagnostic_binding_uses_isolated_placeholder_screen_not_audio_screen():
    source = _main_source()

    assert "SRK_DIAG_SCREEN_TIMING_INTERRUPT_TEST" in source
    assert "MIDI / 68K SILENT PROOF" in source
    assert "Protocol only - no MIDI SCSP note" in source
    assert "SRK_DIAG_SCREEN_AUDIO_TEST" not in source


def test_diagnostic_binding_requires_release_then_fresh_a_press():
    source = _main_source()

    assert "srk_midi_68k_proof_screen_armed = 0;" in source
    assert "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u" in source
    assert "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u" in source
    assert "Release A to arm proof action" in source
    assert "A Run explicit silent proof" in source


def test_diagnostic_binding_resets_explicitly_then_begins_and_polls_nonblocking():
    source = _main_source()

    reset_call = "srk_saturn_midi_68k_physical_proof_reset(&srk_midi_68k_proof);"
    begin_call = "srk_saturn_midi_68k_physical_proof_begin(&srk_midi_68k_proof)"
    poll_call = "srk_saturn_midi_68k_physical_proof_poll(&srk_midi_68k_proof)"

    assert source.count(begin_call) == 1
    assert source.count(poll_call) == 1
    assert source.count(reset_call) == 2
    assert source.index(reset_call) < source.index(begin_call)
    assert "SRK_MIDI_68K_RUNTIME_RUNNING" in source


def test_diagnostic_binding_surfaces_exact_acknowledgement_telemetry():
    source = _main_source()

    assert "srk_midi_68k_proof.telemetry.flags" in source
    assert "srk_midi_68k_proof.telemetry.read_sequence == 1u" in source
    assert "srk_midi_68k_proof.telemetry.read_index == 1u" in source
    assert "srk_midi_68k_proof.telemetry.last_error == 0u" in source
    assert "Success: sequence=1 index=1 error=0" in source
    assert 'return "PASS";' in source
    assert 'return "FAIL";' in source
