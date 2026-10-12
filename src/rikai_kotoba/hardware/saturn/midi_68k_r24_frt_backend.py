"""C89 renderer for the R24 Saturn SH-2 free-running-timer backend.

The generic R24 player accepts monotonic microseconds.  This module supplies a
small Saturn-native backend that samples the SH-2 16-bit FRT, extends wraps and
converts elapsed ticks using a caller-supplied source clock.  The source clock is
not guessed here: the physical candidate must select or calibrate it explicitly.

Rendering/compiling this source performs no hardware I/O.  Hardware access only
exists in the emitted C functions if a later candidate explicitly calls them.
"""

from __future__ import annotations

from .midi_68k_r24_clock import (
    SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS,
    SATURN_MIDI_68K_R24_FRT_DIVIDER,
    SATURN_MIDI_68K_R24_SH2_FRC_H_ADDRESS,
    SATURN_MIDI_68K_R24_SH2_FRC_L_ADDRESS,
    SATURN_MIDI_68K_R24_SH2_TCR_ADDRESS,
    SATURN_MIDI_68K_R24_SH2_TCR_DIV128,
    validate_saturn_midi_68k_r24_clock_contract,
)


class SaturnMidi68KR24FRTBackendError(RuntimeError):
    """Raised when the rendered FRT backend contract changes unexpectedly."""


def validate_saturn_midi_68k_r24_frt_backend_contract() -> None:
    validate_saturn_midi_68k_r24_clock_contract()
    if SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS != 65536:
        raise SaturnMidi68KR24FRTBackendError("R24 FRT counter geometry changed")
    if SATURN_MIDI_68K_R24_FRT_DIVIDER != 128:
        raise SaturnMidi68KR24FRTBackendError("R24 FRT divider changed")
    if SATURN_MIDI_68K_R24_SH2_TCR_DIV128 != 0x02:
        raise SaturnMidi68KR24FRTBackendError("R24 FRT /128 selector changed")


def render_saturn_midi_68k_r24_frt_backend_header() -> str:
    validate_saturn_midi_68k_r24_frt_backend_contract()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R24_FRT_BACKEND_H",
            "#define SRK_SATURN_MIDI_68K_R24_FRT_BACKEND_H",
            "",
            "typedef struct SRK_MIDI_R24_FRT_CLOCK {",
            "    unsigned short initialized;",
            "    unsigned short last_counter;",
            "    unsigned long extended_ticks;",
            "    unsigned long origin_ticks;",
            "    unsigned long elapsed_us;",
            "} SRK_MIDI_R24_FRT_CLOCK;",
            "",
            "void srk_saturn_midi_r24_frt_reset(SRK_MIDI_R24_FRT_CLOCK *state);",
            "void srk_saturn_midi_r24_frt_configure_div128(void);",
            "unsigned short srk_saturn_midi_r24_frt_read_counter(void);",
            "unsigned long srk_saturn_midi_r24_frt_sample_us(",
            "    SRK_MIDI_R24_FRT_CLOCK *state,",
            "    unsigned long source_hz);",
            "",
            "#endif",
            "",
        )
    )


def render_saturn_midi_68k_r24_frt_backend_source() -> str:
    validate_saturn_midi_68k_r24_frt_backend_contract()
    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_r24_frt_backend.h"',
            "",
            f"#define SRK_R24_FRT_FRC_H (*(volatile unsigned char *)0x{SATURN_MIDI_68K_R24_SH2_FRC_H_ADDRESS:08X}UL)",
            f"#define SRK_R24_FRT_FRC_L (*(volatile unsigned char *)0x{SATURN_MIDI_68K_R24_SH2_FRC_L_ADDRESS:08X}UL)",
            f"#define SRK_R24_FRT_TCR   (*(volatile unsigned char *)0x{SATURN_MIDI_68K_R24_SH2_TCR_ADDRESS:08X}UL)",
            f"#define SRK_R24_FRT_DIVIDER {SATURN_MIDI_68K_R24_FRT_DIVIDER}UL",
            f"#define SRK_R24_FRT_DIV128_SELECT 0x{SATURN_MIDI_68K_R24_SH2_TCR_DIV128:02X}u",
            "",
            "void srk_saturn_midi_r24_frt_reset(SRK_MIDI_R24_FRT_CLOCK *state)",
            "{",
            "    if(!state) return;",
            "    state->initialized = 0u;",
            "    state->last_counter = 0u;",
            "    state->extended_ticks = 0UL;",
            "    state->origin_ticks = 0UL;",
            "    state->elapsed_us = 0UL;",
            "}",
            "",
            "void srk_saturn_midi_r24_frt_configure_div128(void)",
            "{",
            "    unsigned char value;",
            "    value = SRK_R24_FRT_TCR;",
            "    value = (unsigned char)((value & 0xFCu) | SRK_R24_FRT_DIV128_SELECT);",
            "    SRK_R24_FRT_TCR = value;",
            "}",
            "",
            "unsigned short srk_saturn_midi_r24_frt_read_counter(void)",
            "{",
            "    unsigned char high_before;",
            "    unsigned char high_after;",
            "    unsigned char low;",
            "    do {",
            "        high_before = SRK_R24_FRT_FRC_H;",
            "        low = SRK_R24_FRT_FRC_L;",
            "        high_after = SRK_R24_FRT_FRC_H;",
            "    } while(high_before != high_after);",
            "    return (unsigned short)(((unsigned short)high_after << 8) | low);",
            "}",
            "",
            "unsigned long srk_saturn_midi_r24_frt_sample_us(",
            "    SRK_MIDI_R24_FRT_CLOCK *state,",
            "    unsigned long source_hz)",
            "{",
            "    unsigned short counter;",
            "    unsigned long delta;",
            "    unsigned long elapsed_ticks;",
            "    unsigned long long numerator;",
            "",
            "    if(!state || source_hz == 0UL) return 0UL;",
            "    counter = srk_saturn_midi_r24_frt_read_counter();",
            "    if(!state->initialized){",
            "        state->initialized = 1u;",
            "        state->last_counter = counter;",
            "        state->extended_ticks = (unsigned long)counter;",
            "        state->origin_ticks = (unsigned long)counter;",
            "        state->elapsed_us = 0UL;",
            "        return 0UL;",
            "    }",
            "",
            "    if(counter >= state->last_counter)",
            "        delta = (unsigned long)(counter - state->last_counter);",
            "    else",
            f"        delta = {SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS}UL - (unsigned long)state->last_counter + (unsigned long)counter;",
            "    state->last_counter = counter;",
            "    state->extended_ticks += delta;",
            "    elapsed_ticks = state->extended_ticks - state->origin_ticks;",
            "    numerator = (unsigned long long)elapsed_ticks * 1000000ULL * SRK_R24_FRT_DIVIDER;",
            "    state->elapsed_us = (unsigned long)(numerator / (unsigned long long)source_hz);",
            "    return state->elapsed_us;",
            "}",
            "",
        )
    )
