"""R22A correction for the R22 physical-proof selected-state capture seam.

Real Saturn R22 evidence reached sequence 2, processed 40 records across two
batches, passed every timing/refill milestone, and passed the complete 1408-word
state verifier.  The terminal proof nevertheless reported E014 because the
redundant selected-state capture treated channel-summary *word indexes* as byte
offsets.  R22A preserves the accepted resident stream engine and proof program
and corrects only those generated capture addresses.
"""

from __future__ import annotations

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT,
    SATURN_MIDI_68K_CH_PITCH_BEND,
    SATURN_MIDI_68K_CH_PROGRAM,
    SATURN_MIDI_68K_CHANNEL_STATE_BYTES,
    SATURN_MIDI_68K_STATE_ADDRESS,
)
from .midi_68k_resident_stream_physical_candidate import (
    SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL,
    build_srk_saturn_midi_68k_stream_expected_words,
    build_srk_saturn_midi_68k_stream_physical_program,
    build_srk_saturn_midi_68k_stream_physical_snapshot,
    derive_resident_stream_candidate_main,
    derive_resident_stream_candidate_menu,
    render_srk_saturn_midi_68k_stream_physical_proof_header,
    render_srk_saturn_midi_68k_stream_physical_proof_source as _render_r22_source,
)


R22_PHYSICAL_FAILURE_CODE = 0xE014
R22_PHYSICAL_FAILURE_FINAL_PITCH = 64
R22A_CORRECTION_LABEL = "R22A selected-state capture byte-address correction"


def _channel_base() -> int:
    return (
        SATURN_MIDI_68K_STATE_ADDRESS
        + SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL * SATURN_MIDI_68K_CHANNEL_STATE_BYTES
    )


def _word_address(word_index: int) -> int:
    """Translate a channel-summary word index to its Sound-RAM byte address."""

    return _channel_base() + int(word_index) * 2


def r22a_selected_state_addresses() -> tuple[int, int, int]:
    """Return corrected program, pitch-bend, and active-count byte addresses."""

    return (
        _word_address(SATURN_MIDI_68K_CH_PROGRAM),
        _word_address(SATURN_MIDI_68K_CH_PITCH_BEND),
        _word_address(SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT),
    )


def render_srk_saturn_midi_68k_stream_physical_proof_source_r22a() -> str:
    """Render the R22 proof with only the selected-state capture addresses fixed."""

    source = _render_r22_source()
    base = _channel_base()
    corrected_program, corrected_pitch, corrected_active = r22a_selected_state_addresses()

    # Program is word index 0, so the R22 expression happened to be correct.
    program_line = f"#define SRK_STREAM_PROOF_PROGRAM_ADDRESS 0x{corrected_program:08X}UL"
    if source.count(program_line) != 1:
        raise RuntimeError("R22 program capture address no longer matches reviewed evidence")

    wrong_pitch = base + SATURN_MIDI_68K_CH_PITCH_BEND
    wrong_active = base + SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT
    wrong_pitch_line = f"#define SRK_STREAM_PROOF_PITCH_ADDRESS 0x{wrong_pitch:08X}UL"
    wrong_active_line = f"#define SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS 0x{wrong_active:08X}UL"
    fixed_pitch_line = f"#define SRK_STREAM_PROOF_PITCH_ADDRESS 0x{corrected_pitch:08X}UL"
    fixed_active_line = f"#define SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS 0x{corrected_active:08X}UL"

    if source.count(wrong_pitch_line) != 1:
        raise RuntimeError("R22 pitch capture defect signature is no longer isolated")
    if source.count(wrong_active_line) != 1:
        raise RuntimeError("R22 active-count capture defect signature is no longer isolated")

    corrected = source.replace(wrong_pitch_line, fixed_pitch_line, 1)
    corrected = corrected.replace(wrong_active_line, fixed_active_line, 1)

    for forbidden in (wrong_pitch_line, wrong_active_line):
        if forbidden in corrected:
            raise RuntimeError("R22A still contains a reviewed bad capture address")
    for required in (program_line, fixed_pitch_line, fixed_active_line):
        if corrected.count(required) != 1:
            raise RuntimeError("R22A corrected capture address is missing or duplicated")

    return corrected
