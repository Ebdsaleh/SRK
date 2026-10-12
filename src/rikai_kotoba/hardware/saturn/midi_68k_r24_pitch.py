"""R24 musically calibrated MIDI-note -> SCSP pitch model.

R23 intentionally used a diagnostic 100-sample loop with MIDI note 60 mapped to
SCSP pitch zero.  The physical result was audible but measured around 440 Hz, so
that mapping proved transport/keying rather than musical pitch.

R24 keeps the physically proven 100-sample waveform but treats its nominal
zero-pitch fundamental as 441 Hz (44.1 kHz / 100 samples) and encodes the SCSP
OCT/FNS multiplier required for each equal-tempered MIDI note.  The resulting
quantisation error is below one cent across MIDI 0..127.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


SATURN_MIDI_68K_R24_SAMPLE_RATE_HZ = 44100.0
SATURN_MIDI_68K_R24_WAVEFORM_SAMPLES = 100
SATURN_MIDI_68K_R24_BASE_FREQUENCY_HZ = (
    SATURN_MIDI_68K_R24_SAMPLE_RATE_HZ / SATURN_MIDI_68K_R24_WAVEFORM_SAMPLES
)
SATURN_MIDI_68K_R24_A4_NOTE = 69
SATURN_MIDI_68K_R24_A4_HZ = 440.0
SATURN_MIDI_68K_R24_MAX_ACCEPTED_ERROR_CENTS = 1.0


class SaturnMidi68KR24PitchError(RuntimeError):
    """Raised when an R24 pitch cannot be represented by the SCSP OCT/FNS field."""


@dataclass(frozen=True)
class SaturnMidi68KR24PitchPoint:
    note: int
    target_hz: float
    pitch_word: int
    actual_hz: float
    error_cents: float


def midi_note_frequency_hz(note: int, *, a4_hz: float = SATURN_MIDI_68K_R24_A4_HZ) -> float:
    if note < 0 or note > 127:
        raise SaturnMidi68KR24PitchError("MIDI note is outside 0..127")
    if not math.isfinite(a4_hz) or a4_hz <= 0.0:
        raise SaturnMidi68KR24PitchError("A4 frequency must be positive and finite")
    return a4_hz * (2.0 ** ((note - SATURN_MIDI_68K_R24_A4_NOTE) / 12.0))


def decode_scsp_pitch_multiplier(pitch_word: int) -> float:
    """Decode the SCSP OCT/FNS playback-rate multiplier."""

    if pitch_word < 0 or pitch_word > 0x7FFF:
        raise SaturnMidi68KR24PitchError("SCSP pitch word is outside 15-bit range")
    octave_raw = (pitch_word >> 11) & 0x0F
    octave = octave_raw - 16 if octave_raw & 0x08 else octave_raw
    fns = pitch_word & 0x03FF
    return (2.0 ** octave) * (1.0 + (fns / 1024.0))


def encode_scsp_pitch_multiplier(multiplier: float) -> int:
    """Return the nearest SCSP OCT/FNS representation of a positive multiplier."""

    if not math.isfinite(multiplier) or multiplier <= 0.0:
        raise SaturnMidi68KR24PitchError("SCSP pitch multiplier must be positive and finite")

    octave = math.floor(math.log2(multiplier))
    fraction = (multiplier / (2.0 ** octave)) - 1.0
    fns = int(fraction * 1024.0 + 0.5)
    if fns >= 1024:
        octave += 1
        fns = 0
    if octave < -8 or octave > 7:
        raise SaturnMidi68KR24PitchError(
            f"SCSP OCT cannot represent multiplier {multiplier!r}"
        )
    if fns < 0 or fns > 0x03FF:
        raise SaturnMidi68KR24PitchError("SCSP FNS calculation escaped 10-bit range")
    return ((octave & 0x0F) << 11) | fns


def build_saturn_midi_68k_r24_pitch_point(note: int) -> SaturnMidi68KR24PitchPoint:
    target_hz = midi_note_frequency_hz(note)
    multiplier = target_hz / SATURN_MIDI_68K_R24_BASE_FREQUENCY_HZ
    pitch_word = encode_scsp_pitch_multiplier(multiplier)
    actual_hz = (
        SATURN_MIDI_68K_R24_BASE_FREQUENCY_HZ
        * decode_scsp_pitch_multiplier(pitch_word)
    )
    error_cents = 1200.0 * math.log2(actual_hz / target_hz)
    return SaturnMidi68KR24PitchPoint(
        note=note,
        target_hz=target_hz,
        pitch_word=pitch_word,
        actual_hz=actual_hz,
        error_cents=error_cents,
    )


def midi_note_to_calibrated_scsp_pitch(note: int) -> int:
    return build_saturn_midi_68k_r24_pitch_point(note).pitch_word


def build_saturn_midi_68k_r24_pitch_table() -> tuple[int, ...]:
    points = tuple(build_saturn_midi_68k_r24_pitch_point(note) for note in range(128))
    worst = max(abs(point.error_cents) for point in points)
    if worst >= SATURN_MIDI_68K_R24_MAX_ACCEPTED_ERROR_CENTS:
        raise SaturnMidi68KR24PitchError(
            f"R24 pitch table exceeds one-cent error budget: {worst:.6f} cents"
        )
    return tuple(point.pitch_word for point in points)


def validate_saturn_midi_68k_r24_pitch_table() -> None:
    """Lock musical reference points and the full-table error budget."""

    table = build_saturn_midi_68k_r24_pitch_table()
    if len(table) != 128:
        raise SaturnMidi68KR24PitchError("R24 pitch table no longer has 128 entries")

    # The R23 proof established that the physical 100-sample zero-pitch loop is
    # around A4.  R24 therefore calibrates note 69 near 440 Hz rather than
    # preserving R23's diagnostic note-60 root.
    a4 = build_saturn_midi_68k_r24_pitch_point(69)
    if abs(a4.actual_hz - 440.0) >= 0.25:
        raise SaturnMidi68KR24PitchError("R24 A4 calibration escaped 440 Hz tolerance")

    for note in (0, 48, 60, 69, 71, 74, 76, 79, 83, 86, 127):
        point = build_saturn_midi_68k_r24_pitch_point(note)
        if abs(point.error_cents) >= SATURN_MIDI_68K_R24_MAX_ACCEPTED_ERROR_CENTS:
            raise SaturnMidi68KR24PitchError(
                f"R24 note {note} exceeds pitch error budget: {point.error_cents:.6f} cents"
            )
