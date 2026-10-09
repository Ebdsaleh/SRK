"""Prepare, build, verify and optionally deploy one fresh Saturn candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN,
)
from rikai_kotoba.hardware.saturn.saroo.standalone_workflow import (
    run_saturn_standalone_saroo_workflow,
)


_REVISION_RE = re.compile(r"R[1-9][0-9]*\Z", re.IGNORECASE)
_DEFAULT_TEMPLATE = Path(
    "SaturnOrbit-Inspect/payload/app/EXAMPLES/CharlesMacDonald/vdp1ex"
)
_DEFAULT_IP_BIN = Path("SaturnOrbit-Inspect/payload/app/COMMON/IP.BIN")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-saroo-candidate",
        description=(
            "Create one fresh SRK Saturn diagnostics revision, build and verify it, "
            "validate its SAROO destination, then optionally perform exactly one "
            "guarded card deployment followed by whole-card verification."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root containing the reviewed local toolchain/assets",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Off-card SRK workspace root used for pre-deployment guard manifests",
    )
    parser.add_argument("--card-root", required=True, help="Mounted SAROO SD-card root")
    parser.add_argument(
        "--revision",
        required=True,
        help="Fresh diagnostics revision such as R11; used only for new paths/names",
    )
    parser.add_argument(
        "--release-date",
        help="Saturn System ID date as YYYYMMDD (defaults to current UTC date)",
    )
    parser.add_argument(
        "--category",
        default="TEST",
        help="Existing SAROO/ISO category (default: TEST)",
    )
    parser.add_argument(
        "--template",
        help="Optional reviewed vdp1ex template override",
    )
    parser.add_argument(
        "--ip-bin",
        help="Optional reviewed Saturn IP.BIN override",
    )
    parser.add_argument(
        "--output",
        help="Optional fresh generated-project path override",
    )
    parser.add_argument(
        "--name",
        help="Optional fresh SAROO destination-name override",
    )
    parser.add_argument(
        "--guard-manifest",
        help="Optional off-card pre-write inventory path override",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="After all read-only/build gates pass, perform the one guarded SD-card write",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply; must be exactly {CONFIRMATION_TOKEN}",
    )
    return parser


def _resolved_arguments(args, parser: argparse.ArgumentParser):
    revision = str(args.revision).upper()
    if _REVISION_RE.fullmatch(revision) is None:
        parser.error("--revision must use the form R<number>, for example R11")

    release_date = args.release_date or datetime.now(timezone.utc).strftime("%Y%m%d")
    if len(release_date) != 8 or not release_date.isdigit():
        parser.error("--release-date must be exactly YYYYMMDD")

    saturn_root = Path(args.saturn_root).expanduser()
    workspace = Path(args.workspace).expanduser()
    template = Path(args.template).expanduser() if args.template else saturn_root / _DEFAULT_TEMPLATE
    ip_bin = Path(args.ip_bin).expanduser() if args.ip_bin else saturn_root / _DEFAULT_IP_BIN
    output = (
        Path(args.output).expanduser()
        if args.output
        else saturn_root / f"SRK-Diagnostics-R1-{revision}"
    )
    name = args.name or f"SRK-Diagnostics-{revision}"
    guard_manifest = (
        Path(args.guard_manifest).expanduser()
        if args.guard_manifest
        else workspace
        / "Backups"
        / "SAROO"
        / f"card_before_srk_diagnostics_{revision.lower()}_{release_date}.json"
    )
    return (
        revision,
        release_date,
        template,
        ip_bin,
        output,
        name,
        guard_manifest,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    (
        revision,
        release_date,
        template,
        ip_bin,
        output,
        name,
        guard_manifest,
    ) = _resolved_arguments(args, parser)

    try:
        result = run_saturn_standalone_saroo_workflow(
            args.saturn_root,
            template,
            ip_bin,
            output,
            args.card_root,
            guard_manifest,
            release_date=release_date,
            destination_name=name,
            category=args.category,
            apply=args.apply,
            confirmation=args.confirm,
        )
    except Exception as exc:
        print(
            f"srk-saturn-saroo-candidate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print(f"SRK Saturn candidate {revision}")
    print("-" * 48)
    print(f"Project          : {result.project.output_root}")
    print(f"Build result     : {'SUCCESS' if result.build.successful else 'FAILED'}")
    print(f"Build report     : {result.build.report_path}")
    print(f"Destination plan : {result.plan.destination_directory}")
    print(f"BIN SHA-256      : {result.plan.bin_sha256}")
    print(f"CUE SHA-256      : {result.plan.cue_sha256}")
    print(f"MODE1 sectors    : {result.plan.sector_count}")

    if not result.applied:
        print()
        print("Result            : READ-ONLY CANDIDATE READY")
        print("SAROO writes      : none")
        print("Guard manifest    : not created (no write requested)")
        print("To perform the full guarded transfer in one run, use:")
        print(f"  --apply --confirm {CONFIRMATION_TOKEN}")
        return 0

    assert result.guard is not None
    assert result.deployment is not None
    assert result.verification is not None
    print(f"Guard manifest    : {result.guard.manifest_path}")
    print(f"Guard SHA-256     : {result.guard.manifest_sha256}")
    print(f"Destination BIN   : {result.deployment.destination_bin}")
    print(f"Destination CUE   : {result.deployment.destination_cue}")
    print(f"Card files        : {result.verification.file_count}")
    print(f"Card directories  : {result.verification.directory_count}")
    print(f"Card bytes        : {result.verification.total_file_bytes}")
    print(f"Card files hashed : {result.verification.hashed_file_count}")
    print("Whole-card result : MATCH")
    print()
    print("Result            : VERIFIED AND SAFE TO EJECT")
    print("Only the new candidate directory and its verified BIN/CUE were allowed to differ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
