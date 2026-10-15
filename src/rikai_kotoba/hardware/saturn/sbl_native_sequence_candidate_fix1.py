"""Compatibility fix for the first native SDDRV Space Spectre candidate build.

The GATE3 candidate architecture remains unchanged: authored M6 sequence data is
loaded with ``SND_KD_SEQ`` and started with ``SND_StartSeq``.  This wrapper only
narrows the SH-2 status/telemetry surface and restores Sega's documented total-
volume setup before sequence start.

The first GATE3 host build failed before any media write.  Until the exact legacy
compiler/linker diagnostic is available, do not add more SBL dependencies than
playback actually needs.  ``SND_GetSeqPlayPos`` is optional telemetry; sequence
completion only requires ``SND_GetSeqStat``.  Sega's Sound I/F calling sequence
also sets total volume before ``SND_StartSeq``.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from . import sbl_native_sequence_candidate as _base


SaturnSblNativeSequenceCandidateError = _base.SaturnSblNativeSequenceCandidateError
SaturnSblNativeSequenceAssets = _base.SaturnSblNativeSequenceAssets
SaturnSblNativeSequenceCandidateResult = _base.SaturnSblNativeSequenceCandidateResult
_ORIGINAL_RUNTIME = _base._runtime
_ORIGINAL_MAIN = _base._native_main


class SaturnSblNativeSequenceCandidateFix1Error(SaturnSblNativeSequenceCandidateError):
    """Raised when the narrowed native-sequence compatibility build fails."""


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SaturnSblNativeSequenceCandidateFix1Error(
            f"native candidate fix1 anchor changed: {label}"
        )
    return text.replace(old, new, 1)


def _patched_runtime() -> str:
    runtime = _ORIGINAL_RUNTIME()

    runtime = _replace_once(
        runtime,
        "#define ERR_START 7u\n",
        "#define ERR_START 7u\n#define ERR_VOLUME 8u\n",
        "error constants",
    )

    move_and_start = (
        " SND_MoveData((Uint16 *)sequence,(Uint32)SRK_SBL_GM_SEQUENCE_BYTES,"
        "SND_KD_SEQ,0);\n"
        " r=SND_StartSeq(1,0,0,1);s->last_ret=(unsigned int)r;\n"
    )
    move_volume_start = (
        " SND_MoveData((Uint16 *)sequence,(Uint32)SRK_SBL_GM_SEQUENCE_BYTES,"
        "SND_KD_SEQ,0);\n"
        " r=SND_SetTlVl(15);s->last_ret=(unsigned int)r;"
        "if(r!=SND_RET_SET){fail(s,ERR_VOLUME);return 0u;}\n"
        " r=SND_StartSeq(1,0,0,1);s->last_ret=(unsigned int)r;\n"
    )
    runtime = _replace_once(
        runtime,
        move_and_start,
        move_volume_start,
        "sequence move/start",
    )

    runtime = _replace_once(
        runtime,
        " SndSeqStat stat;SndSeqPlayPos pos;unsigned int mode;if(!s)return 0u;\n",
        " SndSeqStat stat;unsigned int mode;if(!s)return 0u;\n",
        "status locals",
    )
    runtime = _replace_once(
        runtime,
        " SND_GetSeqStat(&stat,1);SND_GetSeqPlayPos(&pos,1);\n",
        " SND_GetSeqStat(&stat,1);\n",
        "status acquisition",
    )
    runtime = _replace_once(
        runtime,
        " mode=(unsigned int)SND_SEQ_STAT_MODE(stat);s->event_index=(unsigned long)pos;"
        "s->retries=(unsigned long)SND_SEQ_STAT_STAT(stat);\n",
        " mode=(unsigned int)SND_SEQ_STAT_MODE(stat);s->event_index=(unsigned long)mode;"
        "s->retries=(unsigned long)SND_SEQ_STAT_STAT(stat);\n",
        "status storage",
    )

    if "SND_GetSeqPlayPos" in runtime or "SndSeqPlayPos" in runtime:
        raise SaturnSblNativeSequenceCandidateFix1Error(
            "native candidate fix1 still depends on sequence-position telemetry"
        )
    if "SND_SetTlVl(15)" not in runtime or "SND_GetSeqStat" not in runtime:
        raise SaturnSblNativeSequenceCandidateFix1Error(
            "native candidate fix1 lost documented sequence startup/status calls"
        )
    if "SND_CtrlDirMidi" in runtime:
        raise SaturnSblNativeSequenceCandidateFix1Error(
            "native candidate fix1 regressed to Direct MIDI"
        )
    return runtime


def _patched_main(base: str) -> str:
    main = _ORIGINAL_MAIN(base)
    if 'gm_field(2,7,9,"Position:")' in main:
        main = main.replace(
            'gm_field(2,7,9,"Position:")',
            'gm_field(2,7,9,"Mode:")',
            1,
        )
    return main


@contextmanager
def _compatibility_patch():
    previous_runtime = _base._runtime
    previous_main = _base._native_main
    _base._runtime = _patched_runtime
    _base._native_main = _patched_main
    try:
        yield
    finally:
        _base._runtime = previous_runtime
        _base._native_main = previous_main


def _build_log_tail(output_directory: Path, limit: int = 48) -> str:
    log = output_directory / "SRK_STANDALONE_BUILD_LOG.txt"
    if not log.is_file():
        return ""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-limit:])


def build_saturn_sbl_native_sequence_candidate(
    baseline_project,
    sequence_directory,
    saturn_root,
    output_directory,
) -> SaturnSblNativeSequenceCandidateResult:
    """Build GATE3 with the minimum documented native SDDRV playback surface."""

    output = Path(output_directory).expanduser().resolve(strict=False)
    try:
        with _compatibility_patch():
            return _base.build_saturn_sbl_native_sequence_candidate(
                baseline_project,
                sequence_directory,
                saturn_root,
                output_directory,
            )
    except SaturnSblNativeSequenceCandidateError as exc:
        tail = _build_log_tail(output)
        if tail:
            raise SaturnSblNativeSequenceCandidateFix1Error(
                f"{exc}\n--- SRK_STANDALONE_BUILD_LOG tail ---\n{tail}"
            ) from exc
        raise
