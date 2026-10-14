"""R26 FIX1 presentation derivation for the physical Space Spectre retry.

FIX1 keeps the accepted R26 proof/runtime contract but makes the terminal status
line truthful.  The failed first physical run exposed that the inherited R24
screen always rendered the configured success sentence even while the proof was
in ERROR.  This wrapper shows PASS only in phase 5, a clear ERROR sentence in
phase 6, and a running message beforehand.
"""

from __future__ import annotations

from . import midi_68k_r26_physical_candidate as _r26


_FIX1_SUBTITLE = "Space Spectre FIX1 - 9154 events / 16v"
_FIX1_MENU_LABEL = "MIDI R26 Space Spectre F1"


def derive_r26_fix1_candidate_main(r24_main: str) -> str:
    main = _r26.derive_r26_double_impact_candidate_main(r24_main)

    old_subtitle = '#define SRK_MIDI_68K_PROOF_SUBTITLE "Space Spectre - 9154 events / 16v"'
    new_subtitle = f'#define SRK_MIDI_68K_PROOF_SUBTITLE "{_FIX1_SUBTITLE}"'
    if main.count(old_subtitle) != 1:
        raise RuntimeError("R26 subtitle shape changed before FIX1")
    main = main.replace(old_subtitle, new_subtitle, 1)

    old = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    new = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
            "    if (srk_midi_68k_proof.telemetry.phase == 5u) {",
            "        srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "    } else if (srk_midi_68k_proof.telemetry.phase == 6u) {",
            '        srk_midi_68k_draw_field(2, 25, 38, "Space Spectre ERROR - see telemetry");',
            "    } else {",
            '        srk_midi_68k_draw_field(2, 25, 38, "Space Spectre running - wait");',
            "    }",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(old) != 1:
        raise RuntimeError("R26 unconditional success rendering shape changed before FIX1")
    return main.replace(old, new, 1)


def derive_r26_fix1_candidate_menu(r24_menu: str) -> str:
    menu = _r26.derive_r26_double_impact_candidate_menu(r24_menu)
    old = '"MIDI R26 Space Spectre"'
    new = f'"{_FIX1_MENU_LABEL}"'
    if menu.count(old) != 1:
        raise RuntimeError("R26 menu label shape changed before FIX1")
    return menu.replace(old, new, 1)
