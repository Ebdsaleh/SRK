"""Small cross-platform file operations for an SRK-generated Firm_Saturn tree.

Upstream SAROO's historical Makefile uses ``touch``, ``cat`` and ``rm``.  The
SaturnOrbit R1 SH-ELF bundle supplies the compiler and Make driver but does not
ship every one of those Unix-style utilities.  SRK-generated trees use this
helper instead so the build does not depend on unrelated third-party coreutils.

This module is copied into the generated tree.  It is a build helper only; it
does not install or flash firmware.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def _touch(path: str) -> None:
    Path(path).touch()


def _concat(destination: str, sources: list[str]) -> None:
    if not sources:
        raise ValueError("concat requires at least one source file")

    target = Path(destination)
    target_resolved = target.resolve(strict=False)
    source_paths = [Path(source) for source in sources]
    if any(source.resolve(strict=False) == target_resolved for source in source_paths):
        raise ValueError("concat destination must be different from every source")

    with target.open("wb") as output:
        for source in source_paths:
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)


def _remove(path: str) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-platform file operations used by SRK Firm_Saturn builds"
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    touch_parser = subparsers.add_parser("touch")
    touch_parser.add_argument("path")

    concat_parser = subparsers.add_parser("concat")
    concat_parser.add_argument("destination")
    concat_parser.add_argument("sources", nargs="+")

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.operation == "touch":
        _touch(args.path)
    elif args.operation == "concat":
        _concat(args.destination, args.sources)
    elif args.operation == "remove":
        _remove(args.path)
    else:  # pragma: no cover - argparse owns the operation choices.
        raise AssertionError(f"unhandled operation: {args.operation}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
