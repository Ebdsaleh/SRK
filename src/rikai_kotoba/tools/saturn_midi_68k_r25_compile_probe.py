"""CLI for the R25 inert 32-value RR compiler matrix."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r25_compile_probe import (
    SaturnMidi68KR25CompileProbeError,
    probe_saturn_midi_68k_r25_rr_compile_matrix,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r25-compile-probe",
        description="Compile all 32 inert R25 SCSP RR service images without linking or execution.",
    )
    parser.add_argument("--saturn-root", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_r25_rr_compile_matrix(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KR25CompileProbeError, RuntimeError) as exc:
        print(f"srk-saturn-midi-68k-r25-compile-probe: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print("SRK R25 inert SCSP RR compiler matrix")
    print("------------------------------------")
    print(f"Compiler       : {result.compiler}")
    print(f"RR variants    : {len(result.entries)}")
    print("RR selected    : NO")
    print("SCSP execution : NO")
    print("68K execution  : NO")
    print("SAROO writes   : NONE")
    print(f"Report         : {result.report_path}")
    print(f"Result         : {'SUCCESS' if result.successful else 'FAIL'}")
    return 0 if result.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
