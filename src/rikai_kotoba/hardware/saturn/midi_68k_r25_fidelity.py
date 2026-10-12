"""Integrated host-side acceptance model for the R25 fidelity tranche."""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_r24_song import SaturnMidi68KR24SongProfile
from .midi_68k_r25_note_audit import (
    SaturnMidi68KR25NoteAudit,
    audit_saturn_midi_68k_r25_note_spans,
)
from .midi_68k_r25_progress import (
    SaturnMidi68KR25Progress,
    build_saturn_midi_68k_r25_progress,
)
from .midi_68k_r25_release_lifecycle import (
    SaturnMidi68KR25ReleaseState,
    trace_saturn_midi_68k_r25_release_lifecycle,
)
from .midi_68k_r25_rr_calibration import (
    SaturnMidi68KR25RRCalibrationEntry,
    build_saturn_midi_68k_r25_rr_calibration_matrix,
)


@dataclass(frozen=True)
class SaturnMidi68KR25FidelityProfile:
    note_audit: SaturnMidi68KR25NoteAudit
    final_release_state: SaturnMidi68KR25ReleaseState
    progress_checkpoints: tuple[SaturnMidi68KR25Progress, ...]
    rr_calibration: tuple[SaturnMidi68KR25RRCalibrationEntry, ...]


def build_saturn_midi_68k_r25_fidelity_profile(
    profile: SaturnMidi68KR24SongProfile,
) -> SaturnMidi68KR25FidelityProfile:
    audit = audit_saturn_midi_68k_r25_note_spans(profile.program)
    release_trace = trace_saturn_midi_68k_r25_release_lifecycle(profile.program)
    final = release_trace[-1]
    checkpoints = []
    for numerator in range(5):
        elapsed = (profile.duration_us * numerator) // 4
        completed = (profile.record_count * numerator) // 4
        batches = (len(profile.batches) * numerator) // 4
        checkpoints.append(
            build_saturn_midi_68k_r25_progress(
                elapsed_us=elapsed,
                total_us=profile.duration_us,
                completed_records=completed,
                total_records=profile.record_count,
                batch_sequence=batches,
                total_batches=len(profile.batches),
            )
        )
    return SaturnMidi68KR25FidelityProfile(
        note_audit=audit,
        final_release_state=final,
        progress_checkpoints=tuple(checkpoints),
        rr_calibration=build_saturn_midi_68k_r25_rr_calibration_matrix(),
    )
