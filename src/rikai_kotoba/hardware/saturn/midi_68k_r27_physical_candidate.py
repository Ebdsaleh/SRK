"""R27 fidelity-pass presentation wrapper.

The physically accepted R26 FIX1 proof logic remains unchanged. R27 only changes
the diagnostic subtitle so captured hardware evidence is unmistakable.
"""

from __future__ import annotations

from .midi_68k_r26_fix1_physical_candidate import derive_r26_fix1_candidate_main

_R27_SUBTITLE = "Space Spectre R27 F1 - 9154 / 16v"


def derive_r27_fidelity_candidate_main(r24_main: str) -> str:
    main = derive_r26_fix1_candidate_main(r24_main)
    old = '#define SRK_MIDI_68K_PROOF_SUBTITLE "Space Spectre FIX1 - 9154 events / 16v"'
    new = f'#define SRK_MIDI_68K_PROOF_SUBTITLE "{_R27_SUBTITLE}"'
    if main.count(old) != 1:
        raise RuntimeError("FIX1 subtitle shape changed before R27")
    return main.replace(old, new, 1)
