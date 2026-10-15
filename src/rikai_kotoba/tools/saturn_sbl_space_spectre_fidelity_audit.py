"""Audit Space Spectre native sequence and SCSPBIN tone data without hardware."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_fidelity_audit import (
    SaturnSblFidelityAuditError,
    audit_space_spectre_fidelity,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre-fidelity-audit",
        description=(
            "Read-only fidelity gate for the native Space Spectre candidate. "
            "It proves M6 channel events event-by-event and parses the generated "
            "SCSPBIN melodic/drum banks before another physical Saturn run."
        ),
    )
    parser.add_argument("--project", required=True, type=Path,
                        help="existing built native candidate containing cd/SRKGM.BIN and cd/SRKDRUM.BIN")
    parser.add_argument("--sequence", required=True, type=Path,
                        help="locked GATE3B sequence directory containing SPACESEQ.BNK")
    return parser


def _layer_text(layer) -> str:
    return (
        f"L{layer.index} keys={layer.start_note}-{layer.end_note} "
        f"SA=0x{layer.sample_address:05X} base={layer.base_note} "
        f"fine={layer.fine_tune:+d} TL={layer.total_level} VL={layer.velocity_table}"
    )


def _drum_note_text(drum_note) -> str:
    """Render one resolved GM percussion-note summary without relying on object formatting."""

    return f"Note {drum_note.note:3d}: {len(drum_note.layers)} matching layer(s)"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_space_spectre_fidelity(args.project, args.sequence)
    except Exception as exc:
        print(
            f"srk-saturn-sbl-space-spectre-fidelity-audit: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    seq = report.sequence
    print("SRK Space Spectre / OFFLINE FIDELITY AUDIT")
    print("------------------------------------------")
    print(f"Source MIDI SHA-256 : {seq.source_sha256}")
    print(f"Sequence SHA-256    : {seq.sequence_sha256}")
    print(f"Source events       : {seq.source_event_count}")
    print(f"Decoded events      : {seq.decoded_event_count}")
    print(f"End tick            : {seq.end_tick}")
    print(f"Tempo events        : {seq.tempo_event_count}")
    print(f"M6 event equivalence: {'EXACT' if seq.exact else 'FAILED'}")
    print()

    for label, bank in (("Melodic", report.melodic), ("Drum", report.drums)):
        print(f"{label} bank")
        print(f"  Path              : {bank.path}")
        print(f"  SHA-256           : {bank.sha256}")
        print(f"  Bytes             : {bank.size}")
        print(f"  Voices            : {bank.voice_count}")
        print(
            "  Tables            : "
            f"MIX=0x{bank.mixer_offset:04X} VL=0x{bank.velocity_offset:04X} "
            f"PEG=0x{bank.peg_offset:04X} PLFO=0x{bank.plfo_offset:04X}"
        )
        print(f"  Velocity table 0  : {bank.velocity_table0.hex(' ')}")
    print()

    print("Required melodic programs")
    for voice in report.melodic_programs:
        print(f"  Program {voice.index:3d}: layers={voice.layer_count} bend={voice.bend_range}")
        for layer in voice.layers:
            print(f"    {_layer_text(layer)}")
    print()

    print("Required percussion notes / drum voice 0")
    for drum_note in report.drum_notes:
        print(f"  {_drum_note_text(drum_note)}")
        for layer in drum_note.layers:
            print(f"    {_layer_text(layer)}")
    print(
        "  Distinct sample SA : "
        + ", ".join(f"0x{value:05X}" for value in report.distinct_drum_sample_addresses)
    )
    print()
    if len(report.distinct_drum_sample_addresses) < 2:
        print("Tone-bank warning    : REQUIRED DRUM NOTES COLLAPSE TO ONE SAMPLE ADDRESS")
    else:
        print("Tone-bank structure  : PARSED (musical correctness still requires authoring review)")
    print("SAROO writes         : NONE")
    print("Hardware execution   : NONE")
    print("GATE3F deployment    : BLOCKED pending audit interpretation/correction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
