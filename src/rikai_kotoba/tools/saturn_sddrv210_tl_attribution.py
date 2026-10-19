from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_tl_attribution import (
    SaturnSddrv210TlAttributionError,
    audit_sddrv210_tl_attribution,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sddrv210-tl-attribution",
        description=(
            "Read the existing GM calibration SCSPBIN family banks and attribute "
            "the R4 keyed TL=0xFF result to authored TL versus later SDDRV scaling. "
            "No build, SAROO write, or hardware access is performed."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit_sddrv210_tl_attribution(args.project)
    except SaturnSddrv210TlAttributionError as exc:
        print("SRK SDDRV210 TL ATTRIBUTION")
        print("---------------------------")
        print("Result             : FAILED")
        print(f"Reason             : {exc}")
        print("SAROO writes       : NONE")
        return 1

    print("SRK SDDRV210 TL ATTRIBUTION")
    print("---------------------------")
    print(f"Project            : {result.project_root}")
    print(f"Programs           : {len(result.rows)}")
    print(f"Authored TL range  : 0x{result.authored_tl_min:02X}..0x{result.authored_tl_max:02X}")
    print(f"Authored TL=FF     : {len(result.authored_ff_programs)} programs")
    if result.authored_ff_programs:
        print("TL=FF programs     : " + ",".join(str(v) for v in result.authored_ff_programs))
    print()
    print("Selected physical-comparison rows")
    print("Prog Fam/V TL   dB     DS/P VT V100 SA     Loop PCM")
    for program in (0, 15, 16):
        row = result.rows[program]
        print(
            f"{row.program:3d}  {row.family:02d}/{row.local_voice} "
            f"{row.authored_tl:02X} {row.authored_tl_db:6.1f} "
            f"{row.direct_send_pan:02X}   {row.velocity_table_index:02X} "
            f"{row.velocity_level:4d} {row.sample_address:05X} "
            f"{'Y' if row.loop_enabled else 'N'}    {'8' if row.pcm8 else '16'}"
        )
    print()
    if result.authored_ff_programs:
        print("Attribution        : TL=FF IS PRESENT IN AUTHORED SCSPBIN")
        print("Next boundary      : STATIC SOUNDFONT->SCSP TL AUTHORING")
    else:
        print("Attribution        : AUTHORED TL IS BELOW FF")
        print("Next boundary      : SDDRV VELOCITY/VOLUME -> LIVE SCSP TL")
    print("R4 hardware fact   : KEYED TL=0xFF / MX=0xE000 observed")
    print("Probe behavior     : READ ONLY / OFF CARD")
    print("SAROO writes       : NONE")
    print("Result             : SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
