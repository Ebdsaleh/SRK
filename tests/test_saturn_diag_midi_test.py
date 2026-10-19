from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "integrations" / "saturn" / "diagnostics"


def _text(name: str) -> str:
    return (DIAG / name).read_text(encoding="utf-8")


def test_midi_test_is_ninth_screen_without_renumbering_existing_screens():
    menu = _text("srk_diag_menu.h")
    assert "#define SRK_DIAG_MENU_ITEM_COUNT 9" in menu
    assert "SRK_DIAG_SCREEN_SYSTEM_INFORMATION = 7" in menu
    assert "SRK_DIAG_SCREEN_MIDI_TEST = 8" in menu
    assert "MIDI Test / GM Calibration" in _text("srk_diag_menu.c")


def test_midi_test_catalog_covers_all_gm_programs_and_families():
    header = _text("srk_diag_midi_test.h")
    source = _text("srk_diag_midi_test.c")
    assert "SRK_DIAG_MIDI_PROGRAM_COUNT 128u" in header
    assert "SRK_DIAG_MIDI_FAMILY_COUNT 16u" in header
    assert '"Acoustic Grand Piano"' in source
    assert '"Distortion Guitar"' in source
    assert '"Flute"' in source
    assert '"Gunshot"' in source
    assert '"Piano", "Chromatic Percussion", "Organ", "Guitar"' in source


def test_a_button_is_note_gate_not_fixed_duration_trigger():
    app = _text("srk_diag_app.c")
    assert "SRK_DIAG_BUTTON_A" in app
    assert "host->midi_note_on" in app
    assert "srk_diag_input_was_released(&app->input, SRK_DIAG_BUTTON_A)" in app
    assert "host->midi_note_off" in app
    assert "last_hold_us" in app


def test_program_change_stops_active_note_and_pan_uses_shoulders():
    app = _text("srk_diag_app.c")
    assert "srk_diag_midi_note_off(app, host);" in app
    assert "srk_diag_midi_test_move_program(&app->midi, -1)" in app
    assert "srk_diag_midi_test_move_program(&app->midi, 1)" in app
    assert "SRK_DIAG_BUTTON_L" in app
    assert "SRK_DIAG_BUTTON_R" in app
    assert "host->midi_set_pan" in app


def test_review_mark_is_structured_persisted_and_idempotent():
    host = _text("srk_diag_host.h")
    app = _text("srk_diag_app.c")
    midi = _text("srk_diag_midi_test.c")
    assert "SRK_DIAG_MIDI_REVIEW_RECORD" in host
    for field in (
        "program", "family", "channel", "note", "velocity", "pan",
        "saturn_bank", "saturn_voice", "held_us", "frame",
    ):
        assert f"{field};" in host
    assert "host->midi_persist_review" in app
    assert "srk_diag_midi_review_marked(&app->midi, app->midi.program)" in app
    assert "if(state->review_bits[word] & mask)" in midi


def test_first_calibration_pass_is_fixed_c4_velocity_100_channel_1():
    header = _text("srk_diag_midi_test.h")
    app = _text("srk_diag_app.c")
    assert "SRK_DIAG_MIDI_DEFAULT_CHANNEL 0u" in header
    assert "SRK_DIAG_MIDI_DEFAULT_NOTE 60u" in header
    assert "SRK_DIAG_MIDI_DEFAULT_VELOCITY 100u" in header
    assert '"C4 / 60"' in app
    assert '"MIDI channel:"' in app


def test_midi_velocity_is_interactive_without_changing_default_calibration_point():
    header = _text("srk_diag_midi_test.h")
    midi = _text("srk_diag_midi_test.c")
    app = _text("srk_diag_app.c")

    assert "#define SRK_DIAG_MIDI_DEFAULT_VELOCITY 100u" in header
    assert "#define SRK_DIAG_MIDI_VELOCITY_STEP 8u" in header
    assert "srk_diag_midi_test_move_velocity" in header
    assert "if(value < 1)" in midi
    assert "if(value > 127)" in midi
    assert "state->velocity = (srk_u8)value;" in midi
    assert '"B/C Velocity -/+ (1..127)"' in app
    assert "SRK_DIAG_BUTTON_B" in app
    assert "SRK_DIAG_BUTTON_C" in app
    assert "SRK_DIAG_MIDI_VELOCITY_STEP" in app
