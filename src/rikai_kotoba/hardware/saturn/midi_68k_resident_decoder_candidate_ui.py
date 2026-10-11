"""Strict text derivation for the fresh resident-decoder physical candidate UI.

This module never edits repository integration sources. It transforms copies
inside a fresh off-card candidate tree and refuses any unexpected R19 source
shape.
"""

from __future__ import annotations


class SaturnMidi68KResidentDecoderCandidateUIError(RuntimeError):
    """Raised when the accepted R19 UI no longer has the reviewed shape."""


_R19_DEFINE = "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1"
_CANDIDATE_DEFINE = "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1"
_R19_MENU_LABEL = '"MIDI 68K Batch Proof"'
_CANDIDATE_MENU_LABEL = '"MIDI 68K Decoder Proof"'

_C_BACKSLASH = chr(92)
_OLD_GUARD = (
    "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)"
)
_NEW_GUARD = (
    _OLD_GUARD
    + " || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)"
)


def derive_resident_decoder_candidate_main(r19_main: str) -> str:
    """Return a reviewed seven-record decoder candidate main source."""

    if not r19_main.startswith(_R19_DEFINE + "\n"):
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 main no longer begins with the accepted candidate define"
        )

    main = _CANDIDATE_DEFINE + r19_main[len(_R19_DEFINE):]
    guard_count = main.count(_OLD_GUARD)
    if guard_count < 2:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 proof preprocessor guard shape changed"
        )
    main = main.replace(_OLD_GUARD, _NEW_GUARD)

    include = '#include "srk_saturn_midi_68k_physical_proof.h"'
    if main.count(include) != 1:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 physical-proof include shape changed"
        )
    main = main.replace(
        include,
        include
        + "\n#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE"
        + '\n#include "srk_saturn_midi_68k_resident_decoder_physical_proof.h"'
        + "\n#endif",
        1,
    )

    alias_marker = "#ifdef SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE\n"
    if main.count(alias_marker) != 1:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 proof alias block shape changed"
        )
    resident_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_RESIDENT_DECODER_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K DECODER PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "7 runtime records - no MIDI SCSP note"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Success: sequence=1 index=7 error=0"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_resident_decoder_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_resident_decoder_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_resident_decoder_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)",
        )
    ) + "\n"
    main = main.replace(alias_marker, resident_alias, 1)

    last_error_block = "\n".join(
        (
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);",
            '    srk_midi_68k_draw_field(2, 11, 14, "Last error:");',
            "    srk_midi_68k_draw_field(16, 11, 10, number);",
        )
    )
    if main.count(last_error_block) != 1:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 telemetry rendering shape changed"
        )
    resident_progress = (
        last_error_block
        + "\n\n#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "\n".join(
            (
                "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.processed);",
                '    srk_midi_68k_draw_field(2, 12, 14, "Processed:");',
                "    srk_midi_68k_draw_field(16, 12, 10, number);",
                "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.current_record);",
                '    srk_midi_68k_draw_field(2, 13, 14, "Current:");',
                "    srk_midi_68k_draw_field(16, 13, 10, number);",
                "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.decoder_ready);",
                '    srk_midi_68k_draw_field(2, 14, 14, "Decoder ready:");',
                "    srk_midi_68k_draw_field(16, 14, 10, number);",
            )
        )
        + "\n#endif"
    )
    main = main.replace(last_error_block, resident_progress, 1)

    success_line = "    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);"
    if main.count(success_line) != 1:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 success-line rendering shape changed"
        )
    main = main.replace(
        success_line,
        "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        "    srk_midi_68k_draw_field(2, 15, 36, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        "#else\n"
        + success_line
        + "\n#endif",
        1,
    )

    required = (
        _CANDIDATE_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u",
        '"MIDI / 68K DECODER PROOF"',
        '"Success: sequence=1 index=7 error=0"',
        "srk_saturn_midi_68k_resident_decoder_physical_proof_begin",
        "srk_saturn_midi_68k_resident_decoder_physical_proof_poll",
        "srk_midi_68k_proof.telemetry.processed",
        "srk_midi_68k_proof.telemetry.current_record",
        "srk_midi_68k_proof.telemetry.decoder_ready",
        "Release A to arm proof action",
    )
    for marker in required:
        if marker not in main:
            raise SaturnMidi68KResidentDecoderCandidateUIError(
                f"derived decoder candidate main is missing marker: {marker}"
            )
    return main


def derive_resident_decoder_candidate_menu(r19_menu: str) -> str:
    """Rename only the isolated R19 proof menu entry."""

    if r19_menu.count(_R19_MENU_LABEL) != 1:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "R19 proof menu label is no longer isolated"
        )
    menu = r19_menu.replace(_R19_MENU_LABEL, _CANDIDATE_MENU_LABEL, 1)
    if menu.count(_CANDIDATE_MENU_LABEL) != 1:
        raise SaturnMidi68KResidentDecoderCandidateUIError(
            "decoder proof menu label derivation failed"
        )
    return menu
