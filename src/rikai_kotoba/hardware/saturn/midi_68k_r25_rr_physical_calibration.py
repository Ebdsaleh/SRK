"""R25 physical RR calibration source gate.

The accepted R25 resident service deliberately uses the production 120-ms
ownership deadline.  Physical RR calibration must not reuse that deadline or a
slow envelope would be truncated at 120 ms and the measurement would be biased.

This module therefore renders a calibration-only copy of the service with a
2-second ownership/observation window.  The production module is never edited:
its target-release global is changed only for the duration of one synchronous
render/build call and is restored in ``finally``.  The accepted RR16 production
image is hash-pinned before and after every calibration render.

No RR is selected for production here.  ``release_rate`` remains an explicit
required input and the physical result still has to be observed from Saturn
audio because the SCSP slot monitor does not expose envelope level/phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from . import midi_68k_r25_resident_audio_service as _r25
from .midi_68k_r25_envelope import build_saturn_midi_68k_r25_envelope_plan
from .midi_68k_r25_note_audit import SATURN_MIDI_68K_R25_TARGET_RELEASE_US
from .midi_68k_stream_service import build_srk_saturn_midi_stream_batches
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_R25_CALIBRATION_CHANNEL = 0
SATURN_MIDI_68K_R25_CALIBRATION_NOTE = 69  # A4
SATURN_MIDI_68K_R25_CALIBRATION_VELOCITY = 100
SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US = 250_000
SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US = 1_250_000
SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US = 2_000_000
SATURN_MIDI_68K_R25_CALIBRATION_END_US = (
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US
    + SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US
)

# Accepted Eridu compiler-matrix anchor at ce0afbb, RR16, production 120-ms policy.
SATURN_MIDI_68K_R25_ACCEPTED_RR16_IMAGE_SHA256 = (
    "002e9d102b88e4f21a64dbeb768eb3c66726493a735487be1ae8194a706ed0a2"
)


class SaturnMidi68KR25RRPhysicalCalibrationError(RuntimeError):
    """Raised when calibration would weaken an accepted R25 invariant."""


@dataclass(frozen=True)
class SaturnMidi68KR25RRPhysicalCalibrationPlan:
    release_rate: int
    eg1_word: int
    eg2_word: int
    channel: int
    note: int
    velocity: int
    note_on_us: int
    note_off_us: int
    observation_window_us: int
    observation_end_us: int
    record_count: int
    batch_count: int
    production_rr_selected: bool
    envelope_readback_available: bool
    measurement_mode: str


_T = TypeVar("_T")


def build_saturn_midi_68k_r25_rr_calibration_program() -> SaturnMidiProgram:
    """Return the deterministic one-note A4 physical-calibration program."""

    records = (
        SaturnMidiRecord(
            SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US,
            SaturnMidiOpcode.NOTE_ON,
            SATURN_MIDI_68K_R25_CALIBRATION_CHANNEL,
            SATURN_MIDI_68K_R25_CALIBRATION_NOTE,
            SATURN_MIDI_68K_R25_CALIBRATION_VELOCITY,
        ),
        SaturnMidiRecord(
            SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US,
            SaturnMidiOpcode.NOTE_OFF,
            SATURN_MIDI_68K_R25_CALIBRATION_CHANNEL,
            SATURN_MIDI_68K_R25_CALIBRATION_NOTE,
            64,
        ),
    )
    program = SaturnMidiProgram(
        records=records,
        duration_us=SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US,
    )
    batches = build_srk_saturn_midi_stream_batches(program)
    if len(batches) != 1 or len(batches[0].records) != 2 or batches[0].sequence != 1:
        raise SaturnMidi68KR25RRPhysicalCalibrationError(
            "R25 RR calibration must remain one deterministic two-record batch"
        )
    return program


def build_saturn_midi_68k_r25_rr_physical_calibration_plan(
    *, release_rate: int
) -> SaturnMidi68KR25RRPhysicalCalibrationPlan:
    """Describe one explicit RR probe without selecting a production RR."""

    envelope = build_saturn_midi_68k_r25_envelope_plan(release_rate=release_rate)
    program = build_saturn_midi_68k_r25_rr_calibration_program()
    batches = build_srk_saturn_midi_stream_batches(program)
    return SaturnMidi68KR25RRPhysicalCalibrationPlan(
        release_rate=release_rate,
        eg1_word=envelope.eg1_word,
        eg2_word=envelope.eg2_word,
        channel=SATURN_MIDI_68K_R25_CALIBRATION_CHANNEL,
        note=SATURN_MIDI_68K_R25_CALIBRATION_NOTE,
        velocity=SATURN_MIDI_68K_R25_CALIBRATION_VELOCITY,
        note_on_us=SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US,
        note_off_us=SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US,
        observation_window_us=SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US,
        observation_end_us=SATURN_MIDI_68K_R25_CALIBRATION_END_US,
        record_count=len(program.records),
        batch_count=len(batches),
        production_rr_selected=False,
        envelope_readback_available=False,
        measurement_mode="operator-observed-audio",
    )


def validate_saturn_midi_68k_r25_production_rr16_anchor() -> None:
    """Require the exact accepted RR16/120-ms image before calibration."""

    if _r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US != SATURN_MIDI_68K_R25_TARGET_RELEASE_US:
        raise SaturnMidi68KR25RRPhysicalCalibrationError(
            "R25 production release target global no longer matches source contract"
        )
    image = _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
        release_rate=16
    )
    if image.sha256 != SATURN_MIDI_68K_R25_ACCEPTED_RR16_IMAGE_SHA256:
        raise SaturnMidi68KR25RRPhysicalCalibrationError(
            "accepted R25 RR16 production image changed before calibration"
        )


def _with_calibration_window(callback: Callable[[], _T]) -> _T:
    validate_saturn_midi_68k_r25_production_rr16_anchor()
    original = _r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US
    if original != SATURN_MIDI_68K_R25_TARGET_RELEASE_US:
        raise SaturnMidi68KR25RRPhysicalCalibrationError(
            "refusing calibration from a non-production R25 release target"
        )
    _r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US = (
        SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US
    )
    try:
        result = callback()
    finally:
        _r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US = original
    validate_saturn_midi_68k_r25_production_rr16_anchor()
    return result


def build_srk_saturn_midi_68k_r25_rr_calibration_service_image(
    *, release_rate: int
) -> _r25.SaturnMidi68KR25ResidentAudioServiceImage:
    """Build one explicit RR image with the calibration-only 2-second window."""

    build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    return _with_calibration_window(
        lambda: _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=release_rate
        )
    )


def render_srk_saturn_midi_68k_r25_rr_calibration_service_header(
    *, release_rate: int
) -> str:
    """Render the R25 resident header under the calibration-only window."""

    build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    return _with_calibration_window(
        lambda: _r25.render_srk_saturn_midi_68k_r25_resident_audio_service_header(
            release_rate=release_rate
        )
    )


def render_srk_saturn_midi_68k_r25_rr_calibration_service_source(
    *, release_rate: int
) -> str:
    """Render constant program data under the calibration-only window."""

    build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    return _with_calibration_window(
        lambda: _r25.render_srk_saturn_midi_68k_r25_resident_audio_service_source(
            release_rate=release_rate
        )
    )
