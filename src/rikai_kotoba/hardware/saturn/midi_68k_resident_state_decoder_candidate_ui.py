"""Strict UI derivation for the Phase-B full-state physical candidate."""

from __future__ import annotations


class SaturnMidi68KResidentStateCandidateUIError(RuntimeError):
    """Raised when the accepted R20 candidate UI no longer has the reviewed shape."""


_R20_DEFINE = "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1"
_STATE_DEFINE = "#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE 1"
_R20_MENU_LABEL = '"MIDI 68K Decoder Proof"'
_STATE_MENU_LABEL = '"MIDI 68K State Proof"'

_C_BACKSLASH = chr(92)
_R20_GUARD = (
    "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE) || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)"
)
_STATE_GUARD = (
    _R20_GUARD
    + " || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)"
)


def derive_resident_state_candidate_main(r20_main: str) -> str:
    """Transform only the copied accepted R20 main into the Phase-B candidate."""

    if not r20_main.startswith(_R20_DEFINE + "\n"):
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 main no longer begins with the accepted candidate define"
        )
    main = _STATE_DEFINE + r20_main[len(_R20_DEFINE):]

    guard_count = main.count(_R20_GUARD)
    if guard_count < 2:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 proof preprocessor guard shape changed"
        )
    main = main.replace(_R20_GUARD, _STATE_GUARD)

    include = '#include "srk_saturn_midi_68k_resident_decoder_physical_proof.h"'
    if main.count(include) != 1:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 resident proof include shape changed"
        )
    main = main.replace(
        include,
        include
        + "\n#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE"
        + '\n#include "srk_saturn_midi_68k_resident_state_physical_proof.h"'
        + "\n#endif",
        1,
    )

    alias_marker = (
        "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        "typedef"
    )
    if main.count(alias_marker) != 1:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 proof alias block shape changed"
        )
    state_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 20u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K STATE PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "20 records - full MIDI state verify"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "State PASS: full MIDI state matched"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_resident_state_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_resident_state_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_resident_state_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)",
            "typedef",
        )
    )
    main = main.replace(alias_marker, state_alias, 1)

    last_error_block = "\n".join(
        (
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);",
            '    srk_midi_68k_draw_field(2, 11, 14, "Last error:");',
            "    srk_midi_68k_draw_field(16, 11, 10, number);",
        )
    )
    if main.count(last_error_block) != 1:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 telemetry rendering shape changed"
        )

    state_lines = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.status);",
            '    srk_midi_68k_draw_field(2, 12, 14, "State verify:");',
            "    srk_midi_68k_draw_field(16, 12, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_program);",
            '    srk_midi_68k_draw_field(2, 13, 14, "CH3 program:");',
            "    srk_midi_68k_draw_field(16, 13, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_bank_msb);",
            '    srk_midi_68k_draw_field(2, 14, 14, "CH3 bank MSB:");',
            "    srk_midi_68k_draw_field(16, 14, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_bank_lsb);",
            '    srk_midi_68k_draw_field(2, 15, 14, "CH3 bank LSB:");',
            "    srk_midi_68k_draw_field(16, 15, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_volume);",
            '    srk_midi_68k_draw_field(2, 16, 14, "CH3 volume:");',
            "    srk_midi_68k_draw_field(16, 16, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_pan);",
            '    srk_midi_68k_draw_field(2, 17, 14, "CH3 pan:");',
            "    srk_midi_68k_draw_field(16, 17, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_expression);",
            '    srk_midi_68k_draw_field(2, 18, 14, "CH3 expression:");',
            "    srk_midi_68k_draw_field(16, 18, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_sustain);",
            '    srk_midi_68k_draw_field(2, 19, 14, "CH3 sustain:");',
            "    srk_midi_68k_draw_field(16, 19, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_pitch_bend);",
            '    srk_midi_68k_draw_field(2, 20, 14, "CH3 pitch:");',
            "    srk_midi_68k_draw_field(16, 20, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_active_note_count);",
            '    srk_midi_68k_draw_field(2, 21, 14, "CH3 active:");',
            "    srk_midi_68k_draw_field(16, 21, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch3_cc74);",
            '    srk_midi_68k_draw_field(2, 22, 14, "CH3 CC74:");',
            "    srk_midi_68k_draw_field(16, 22, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch9_program);",
            '    srk_midi_68k_draw_field(2, 23, 14, "CH9 program:");',
            "    srk_midi_68k_draw_field(16, 23, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify.ch9_active_note_count);",
            '    srk_midi_68k_draw_field(2, 24, 14, "CH9 active:");',
            "    srk_midi_68k_draw_field(16, 24, 10, number);",
            "#endif",
        )
    )
    main = main.replace(last_error_block, last_error_block + "\n\n" + state_lines, 1)

    old_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 15, 36, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#else",
            "    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#endif",
        )
    )
    if main.count(old_success) != 1:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 success rendering shape changed"
        )
    new_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)",
            "    srk_midi_68k_draw_field(2, 15, 36, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#else",
            "    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#endif",
        )
    )
    main = main.replace(old_success, new_success, 1)

    prompt_rows = (
        (
            'srk_midi_68k_draw_field(2, 17, 36, "A ignored while proof is RUNNING");',
            'srk_midi_68k_draw_field(2, 26, 36, "A ignored while proof is RUNNING");',
        ),
        (
            'srk_midi_68k_draw_field(2, 17, 36, "A Run again (explicit reset + begin)");',
            'srk_midi_68k_draw_field(2, 26, 36, "A Run again (explicit reset + begin)");',
        ),
        (
            'srk_midi_68k_draw_field(2, 17, 36, "A Run explicit silent proof");',
            'srk_midi_68k_draw_field(2, 26, 36, "A Run explicit silent proof");',
        ),
        (
            'srk_midi_68k_draw_field(2, 17, 36, "Release A to arm proof action");',
            'srk_midi_68k_draw_field(2, 26, 36, "Release A to arm proof action");',
        ),
        (
            'srk_midi_68k_draw_field(2, 19, 36, "START Return to diagnostics menu");',
            'srk_midi_68k_draw_field(2, 27, 36, "START Return to diagnostics menu");',
        ),
    )
    for old, new in prompt_rows:
        if main.count(old) != 1:
            raise SaturnMidi68KResidentStateCandidateUIError(
                f"R20 prompt rendering shape changed: {old}"
            )
        main = main.replace(old, new, 1)

    required = (
        _STATE_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 20u",
        '"MIDI / 68K STATE PROOF"',
        '"State PASS: full MIDI state matched"',
        "srk_saturn_midi_68k_resident_state_physical_proof_begin",
        "state_verify.status",
        "state_verify.ch3_program",
        "state_verify.ch3_cc74",
        "state_verify.ch9_program",
        'srk_midi_68k_draw_field(2, 26, 36, "Release A to arm proof action");',
        'srk_midi_68k_draw_field(2, 27, 36, "START Return to diagnostics menu");',
    )
    for marker in required:
        if marker not in main:
            raise SaturnMidi68KResidentStateCandidateUIError(
                f"derived state candidate main is missing marker: {marker}"
            )
    return main


def derive_resident_state_candidate_menu(r20_menu: str) -> str:
    """Rename only the accepted R20 proof menu entry in the fresh candidate."""

    if r20_menu.count(_R20_MENU_LABEL) != 1:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "R20 proof menu label is no longer isolated"
        )
    menu = r20_menu.replace(_R20_MENU_LABEL, _STATE_MENU_LABEL, 1)
    if menu.count(_STATE_MENU_LABEL) != 1:
        raise SaturnMidi68KResidentStateCandidateUIError(
            "state proof menu label derivation failed"
        )
    return menu
