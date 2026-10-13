"""CLI: profile the exact Double Impact Space Spectre R26 target."""

from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_TARGET_SLOTS,
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_resident_audio_service import (
    build_srk_saturn_midi_68k_r26_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


def _fmt_values(items: tuple[tuple[int, tuple[int, ...]], ...]) -> str:
    return "; ".join(
        f"ch{channel + 1}={','.join(str(value) for value in values)}"
        for channel, values in items
    ) or "none"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Profile the exact Double Impact Space Spectre MIDI for R26."
    )
    parser.add_argument("--repository-root", type=Path, default=None)
    parser.add_argument("--release-rate", type=int, default=16)
    args = parser.parse_args()

    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(
        args.repository_root,
        slot_capacity=SATURN_MIDI_68K_R26_TARGET_SLOTS,
    )
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(
        release_rate=args.release_rate
    )
    counts = dict(profile.opcode_counts)

    print("SRK R26 Double Impact / Space Spectre source gate")
    print("--------------------------------------------------")
    print(f"Member                     : {profile.member_name}")
    print(f"Member SHA-256             : {profile.member_sha256}")
    print(f"Archive SHA-256            : {profile.archive_sha256}")
    print(f"SMF format / tracks / PPQN : {profile.format_type} / {profile.track_count} / {profile.ticks_per_quarter}")
    print(f"Tempo events               : {profile.tempo_count}")
    print(f"Duration                   : {profile.duration_us} us")
    print(f"SRKM records / batches     : {profile.record_count} / {profile.batch_count}")
    print(f"Note On / Note Off         : {profile.note_on_count} / {profile.note_off_count}")
    print(f"Program Change             : {profile.program_change_count}")
    print(f"Control Change             : {counts.get(SaturnMidiOpcode.CONTROL_CHANGE, 0)}")
    print(f"Pitch Bend                 : {counts.get(SaturnMidiOpcode.PITCH_BEND, 0)}")
    print(f"Channels                   : {','.join(str(ch + 1) for ch in profile.channels)}")
    print(f"Note channels              : {','.join(str(ch + 1) for ch in profile.note_channels)}")
    print(f"Programs                   : {_fmt_values(profile.programs_by_channel)}")
    print(f"Controllers                : {_fmt_values(profile.controllers_by_channel)}")
    print(f"Percussion notes (ch10)    : {','.join(str(note) for note in profile.percussion_notes) or 'none'}")
    print(f"Sustain CC64 events        : {profile.sustain_event_count}")
    print(f"Raw peak polyphony         : {profile.raw_peak_polyphony}")
    print(f"R25-tail peak held / owned : {profile.capacity.peak_held} / {profile.capacity.peak_owned}")
    print(f"R26 slot capacity          : {profile.capacity.slot_capacity}")
    print(f"R26 busy allocations       : {profile.capacity.busy_count}")
    print(f"R26 final held/releasing   : {profile.capacity.final_held} / {profile.capacity.final_releasing}")
    print(f"Resident RR / EG1 / EG2    : {image.release_rate} / 0x{image.eg1_word:04X} / 0x{image.eg2_word:04X}")
    print(f"Resident image words/bytes : {image.word_count} / {image.byte_size}")
    print(f"Resident image SHA-256     : {image.sha256}")
    print("Timbre policy              : 8 melodic GM-family synth timbres + channel-10 percussion")
    print("GM soundfont fidelity      : NOT CLAIMED")
    print("Source asset mutation      : NONE")

    if profile.capacity.busy_count:
        print("Result                     : CAPACITY FAIL")
        return 2
    if len(profile.note_channels) < 2 or profile.program_change_count < 2:
        print("Result                     : TRACK NOT SUFFICIENTLY MULTI-INSTRUMENT")
        return 3
    print("Result                     : R26 SOURCE ENGINE READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
