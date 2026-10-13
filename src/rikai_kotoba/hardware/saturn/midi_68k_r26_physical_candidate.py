"""R26 Double Impact / Space Spectre physical-proof renderer.

The proof binds the validated R26 16-slot resident service to the accepted R24
SH-2 FRT clock/refill transport and the exact hash-locked Space Spectre program.
It waits for the final R25-style release ownership to drain before declaring
PASS; completing the producer alone is not sufficient.
"""

from __future__ import annotations

from . import midi_68k_r24_physical_candidate as _r24
from . import midi_68k_r25_resident_audio_service as _r25
from .midi_68k_r24_physical_candidate import build_srk_saturn_midi_68k_r24_expected_midi_words
from .midi_68k_r26_double_impact import SaturnMidi68KR26DoubleImpactProfile
from .midi_68k_r26_resident_audio_service import (
    SATURN_MIDI_68K_R26_OWNED_SLOTS,
    SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS,
)
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
    SATURN_MIDI_68K_STREAM_FLAG_ERROR,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
)


SATURN_MIDI_68K_R26_PHASE_NOT_STARTED = 0
SATURN_MIDI_68K_R26_PHASE_WAIT_BOOT = 1
SATURN_MIDI_68K_R26_PHASE_PLAYING = 2
SATURN_MIDI_68K_R26_PHASE_DRAINING = 3
SATURN_MIDI_68K_R26_PHASE_VERIFY_STATE = 4
SATURN_MIDI_68K_R26_PHASE_PASS = 5
SATURN_MIDI_68K_R26_PHASE_ERROR = 6
SATURN_MIDI_68K_R26_TIMEOUT_MARGIN_US = 5_000_000

SATURN_MIDI_68K_R26_VERIFY_NOT_RUN = 0
SATURN_MIDI_68K_R26_VERIFY_PASS = 1
SATURN_MIDI_68K_R26_VERIFY_SUMMARY_MISMATCH = 2
SATURN_MIDI_68K_R26_VERIFY_CONTROLLER_MISMATCH = 3
SATURN_MIDI_68K_R26_VERIFY_ACTIVE_NOTE_MISMATCH = 4
SATURN_MIDI_68K_R26_VERIFY_FINAL_CONTRACT_MISMATCH = 5

_R24_DEFINE = "#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1"
_R26_DEFINE = "#define SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE 1"
_R24_MENU_LABEL = '"MIDI 68K Song Proof"'
_R26_MENU_LABEL = '"MIDI R26 Space Spectre"'
_R26_GUARD = (
    _r24._R24_GUARD
    + " || "
    + chr(92)
    + "\n    defined(SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE)"
)


def _render_words(name: str, words: tuple[int, ...]) -> list[str]:
    lines = [f"static const unsigned short {name}[] = {{"]
    for offset in range(0, len(words), 8):
        lines.append(
            "    " + ", ".join(f"0x{word:04X}u" for word in words[offset : offset + 8]) + ","
        )
    lines.extend(("};", ""))
    return lines


def render_srk_saturn_midi_68k_r26_physical_proof_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            '#include "srk_saturn_midi_68k_r24_frt_backend.h"',
            '#include "srk_saturn_midi_68k_r26_player.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R26_PHYSICAL_TELEMETRY {",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "    unsigned short phase;",
            "    unsigned short stream_flags;",
            "    unsigned short current_index;",
            "    unsigned short batch_count;",
            "    unsigned short total_processed;",
            "    unsigned short player_sequence;",
            "    unsigned short player_batch_index;",
            "    unsigned short player_complete;",
            "    unsigned short player_error;",
            "    unsigned short clock_pal;",
            "    unsigned short clock_group_b;",
            "    unsigned long clock_source_hz;",
            "    unsigned long clock_us;",
            "    unsigned short voice_key_on_count;",
            "    unsigned short voice_key_off_count;",
            "    unsigned short voice_busy_count;",
            "    unsigned short voice_held_count;",
            "    unsigned short voice_releasing_count;",
            "    unsigned short voice_owned_count;",
            "    unsigned short voice_peak_held;",
            "    unsigned short voice_peak_owned;",
            "    unsigned short voice_release_cancelled;",
            "    unsigned short voice_last_error;",
            "    unsigned short state_verify_status;",
            "    unsigned short mismatch_region;",
            "    unsigned short mismatch_index;",
            "    unsigned short expected_value;",
            "    unsigned short actual_value;",
            "} SRK_SATURN_MIDI_68K_R26_PHYSICAL_TELEMETRY;",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_R26_PHYSICAL_TELEMETRY telemetry;",
            "    SRK_MIDI_R26_PLAYER_STATE player;",
            "    SRK_MIDI_R24_FRT_CLOCK clock;",
            "    unsigned char original_tcr;",
            "    unsigned char frt_configured;",
            "} SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_r26_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r26_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r26_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE *state);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r26_physical_proof_source(
    profile: SaturnMidi68KR26DoubleImpactProfile,
    *,
    release_rate: int,
) -> str:
    from .midi_68k_r26_physical_proof_source import (
        render_srk_saturn_midi_68k_r26_physical_proof_source as _render,
    )
    return _render(profile, release_rate=release_rate)


def _r26_telemetry_block() -> str:
    return "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.phase);",
            '    srk_midi_68k_draw_field(2, 12, 6, "Phase:");',
            "    srk_midi_68k_draw_field(8, 12, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.total_processed);",
            '    srk_midi_68k_draw_field(13, 12, 8, "Events:");',
            "    srk_midi_68k_draw_field(20, 12, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.batch_count);",
            '    srk_midi_68k_draw_field(28, 12, 5, "Bat:");',
            "    srk_midi_68k_draw_field(33, 12, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_us);",
            '    srk_midi_68k_draw_field(2, 13, 8, "Clock:");',
            "    srk_midi_68k_draw_field(9, 13, 12, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_sequence);",
            '    srk_midi_68k_draw_field(23, 13, 5, "Seq:");',
            "    srk_midi_68k_draw_field(28, 13, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_index);",
            '    srk_midi_68k_draw_field(34, 13, 4, "I:");',
            "    srk_midi_68k_draw_field(37, 13, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_on_count);",
            '    srk_midi_68k_draw_field(2, 14, 5, "On:");',
            "    srk_midi_68k_draw_field(6, 14, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_off_count);",
            '    srk_midi_68k_draw_field(14, 14, 5, "Off:");',
            "    srk_midi_68k_draw_field(18, 14, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_busy_count);",
            '    srk_midi_68k_draw_field(26, 14, 6, "Busy:");',
            "    srk_midi_68k_draw_field(31, 14, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_held_count);",
            '    srk_midi_68k_draw_field(2, 15, 6, "Held:");',
            "    srk_midi_68k_draw_field(7, 15, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_releasing_count);",
            '    srk_midi_68k_draw_field(12, 15, 5, "Rel:");',
            "    srk_midi_68k_draw_field(16, 15, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_owned_count);",
            '    srk_midi_68k_draw_field(21, 15, 5, "Own:");',
            "    srk_midi_68k_draw_field(25, 15, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_release_cancelled);",
            '    srk_midi_68k_draw_field(30, 15, 6, "Cut:");',
            "    srk_midi_68k_draw_field(34, 15, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_peak_held);",
            '    srk_midi_68k_draw_field(2, 16, 7, "PkHeld:");',
            "    srk_midi_68k_draw_field(9, 16, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_peak_owned);",
            '    srk_midi_68k_draw_field(14, 16, 6, "PkOwn:");',
            "    srk_midi_68k_draw_field(20, 16, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify_status);",
            '    srk_midi_68k_draw_field(25, 16, 7, "State:");',
            "    srk_midi_68k_draw_field(31, 16, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_source_hz);",
            '    srk_midi_68k_draw_field(2, 17, 4, "Hz:");',
            "    srk_midi_68k_draw_field(5, 17, 12, number);",
            "#endif",
        )
    )


def derive_r26_double_impact_candidate_main(r24_main: str) -> str:
    if not r24_main.startswith(_R24_DEFINE + "\n"):
        raise RuntimeError("R24 main no longer begins with the accepted candidate define")
    main = _R26_DEFINE + r24_main[len(_R24_DEFINE):]
    if main.count(_r24._R24_GUARD) < 2:
        raise RuntimeError("R24 proof preprocessor guard shape changed")
    main = main.replace(_r24._R24_GUARD, _R26_GUARD)

    r24_include = "\n".join((
        "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
        '#include "srk_saturn_midi_68k_r24_physical_proof.h"',
        "#endif",
    ))
    r26_include = "\n".join((
        "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
        '#include "srk_saturn_midi_68k_r26_physical_proof.h"',
        "#endif",
    ))
    if main.count(r24_include) != 1:
        raise RuntimeError("R24 proof include block shape changed")
    main = main.replace(r24_include, r26_include, 1)

    r24_alias = "\n".join((
        "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
        "typedef SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE",
        "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
        "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 22u",
        '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K REAL SONG"',
        '#define SRK_MIDI_68K_PROOF_SUBTITLE "310 events - FRT clock - two SCSP voices"',
        '#define SRK_MIDI_68K_PROOF_SUCCESS "Song PASS: 310 events / peak voices 2"',
        "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r24_physical_proof_reset",
        "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r24_physical_proof_begin",
        "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r24_physical_proof_poll",
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
    ))
    r26_alias = "\n".join((
        "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
        "typedef SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE",
        "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
        "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 2u",
        '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K DOUBLE IMPACT"',
        '#define SRK_MIDI_68K_PROOF_SUBTITLE "Space Spectre - 9154 events / 16v"',
        '#define SRK_MIDI_68K_PROOF_SUCCESS "Space Spectre PASS - 0 dropped notes"',
        "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r26_physical_proof_reset",
        "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r26_physical_proof_begin",
        "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r26_physical_proof_poll",
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
    ))
    if main.count(r24_alias) != 1:
        raise RuntimeError("R24 proof alias block shape changed")
    main = main.replace(r24_alias, r26_alias, 1)

    r24_telemetry = _r24._r24_telemetry_block()
    if main.count(r24_telemetry) != 1:
        raise RuntimeError("R24 telemetry block shape changed")
    main = main.replace(r24_telemetry, _r26_telemetry_block(), 1)

    r24_success = "\n".join((
        "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
        "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
    ))
    r26_success = "\n".join((
        "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
        "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
    ))
    if main.count(r24_success) != 1:
        raise RuntimeError("R24 success rendering shape changed")
    main = main.replace(r24_success, r26_success, 1)

    for marker in (
        _R26_DEFINE,
        '"MIDI / 68K DOUBLE IMPACT"',
        '"Space Spectre - 9154 events / 16v"',
        "srk_saturn_midi_68k_r26_physical_proof_begin",
        "telemetry.voice_release_cancelled",
        "telemetry.voice_peak_owned",
    ):
        if marker not in main:
            raise RuntimeError(f"derived R26 main missing marker: {marker}")
    return main


def derive_r26_double_impact_candidate_menu(r24_menu: str) -> str:
    if r24_menu.count(_R24_MENU_LABEL) != 1:
        raise RuntimeError("R24 song proof menu label is no longer isolated")
    menu = r24_menu.replace(_R24_MENU_LABEL, _R26_MENU_LABEL, 1)
    if menu.count(_R26_MENU_LABEL) != 1:
        raise RuntimeError("R26 Space Spectre menu derivation failed")
    return menu
