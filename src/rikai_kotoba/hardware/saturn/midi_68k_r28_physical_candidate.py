"""R28 percussion-pass presentation wrapper."""

from __future__ import annotations

from .midi_68k_r27_physical_candidate import derive_r27_fidelity_candidate_main

_R28_SUBTITLE = "Space Spectre R28 P1 - 9154 / 16v"


def derive_r28_percussion_candidate_main(r24_main: str) -> str:
    main = derive_r27_fidelity_candidate_main(r24_main)
    old = '#define SRK_MIDI_68K_PROOF_SUBTITLE "Space Spectre R27 F1 - 9154 / 16v"'
    new = f'#define SRK_MIDI_68K_PROOF_SUBTITLE "{_R28_SUBTITLE}"'
    if main.count(old) != 1:
        raise RuntimeError("R27 subtitle shape changed before R28")
    return main.replace(old, new, 1)
