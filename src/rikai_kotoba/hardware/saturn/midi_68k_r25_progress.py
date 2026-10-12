"""R25 playback-progress model for the Saturn real-SMF proof UI.

R24 deliberately prioritised deterministic execution telemetry over UX, which
made it impossible for a person watching the Saturn to know whether playback was
halfway through or looping.  R25 adds a compact, deterministic elapsed/total
surface suitable for the standalone diagnostic screen.
"""

from __future__ import annotations

from dataclasses import dataclass


class SaturnMidi68KR25ProgressError(RuntimeError):
    """Raised when playback progress is internally inconsistent."""


@dataclass(frozen=True)
class SaturnMidi68KR25Progress:
    elapsed_us: int
    total_us: int
    completed_records: int
    total_records: int
    batch_sequence: int
    total_batches: int
    permille: int
    clock_text: str
    record_text: str
    batch_text: str
    bar_text: str


def format_saturn_midi_68k_r25_clock(time_us: int) -> str:
    if time_us < 0:
        raise SaturnMidi68KR25ProgressError("time_us must be non-negative")
    total_ms = time_us // 1000
    minutes, remainder_ms = divmod(total_ms, 60_000)
    seconds, milliseconds = divmod(remainder_ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def build_saturn_midi_68k_r25_progress_bar(
    permille: int,
    *,
    width: int = 20,
) -> str:
    if permille < 0 or permille > 1000:
        raise SaturnMidi68KR25ProgressError("permille must be within 0..1000")
    if width < 4 or width > 64:
        raise SaturnMidi68KR25ProgressError("progress-bar width must be within 4..64")
    filled = (permille * width + 999) // 1000 if permille else 0
    filled = min(width, filled)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def build_saturn_midi_68k_r25_progress(
    *,
    elapsed_us: int,
    total_us: int,
    completed_records: int,
    total_records: int,
    batch_sequence: int,
    total_batches: int,
    bar_width: int = 20,
) -> SaturnMidi68KR25Progress:
    if total_us <= 0:
        raise SaturnMidi68KR25ProgressError("total_us must be positive")
    if elapsed_us < 0:
        raise SaturnMidi68KR25ProgressError("elapsed_us must be non-negative")
    if total_records <= 0 or completed_records < 0 or completed_records > total_records:
        raise SaturnMidi68KR25ProgressError("record progress is outside its reviewed range")
    if total_batches <= 0 or batch_sequence < 0 or batch_sequence > total_batches:
        raise SaturnMidi68KR25ProgressError("batch progress is outside its reviewed range")

    clamped_elapsed = min(elapsed_us, total_us)
    permille = min(1000, (clamped_elapsed * 1000) // total_us)
    percent = min(100, (permille + 5) // 10)
    elapsed_text = format_saturn_midi_68k_r25_clock(clamped_elapsed)
    total_text = format_saturn_midi_68k_r25_clock(total_us)
    return SaturnMidi68KR25Progress(
        elapsed_us=clamped_elapsed,
        total_us=total_us,
        completed_records=completed_records,
        total_records=total_records,
        batch_sequence=batch_sequence,
        total_batches=total_batches,
        permille=permille,
        clock_text=f"{elapsed_text}/{total_text} {percent:3d}%",
        record_text=f"Events {completed_records:03d}/{total_records:03d}",
        batch_text=f"Batch {batch_sequence:02d}/{total_batches:02d}",
        bar_text=build_saturn_midi_68k_r25_progress_bar(permille, width=bar_width),
    )
