"""Prepare a fresh seven-record resident-decoder physical candidate tree."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_decoder import build_srk_saturn_midi_68k_resident_decoder_image
from .midi_68k_resident_decoder_candidate_baseline import (
    SaturnMidi68KResidentDecoderCandidateBaseline,
    verify_resident_decoder_inert_baseline,
)
from .midi_68k_resident_decoder_candidate_ui import (
    derive_resident_decoder_candidate_main,
    derive_resident_decoder_candidate_menu,
)
from .midi_68k_resident_decoder_physical_binding import (
    render_resident_decoder_installer_header,
    render_resident_decoder_installer_source,
    render_resident_decoder_proof_header,
    render_resident_decoder_proof_source,
    render_resident_decoder_runtime_header,
    render_resident_decoder_runtime_source,
)
from .midi_68k_resident_decoder_physical_candidate import (
    SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
    SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_header,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_source,
)


class SaturnMidi68KResidentDecoderCandidatePrepareError(RuntimeError):
    """Raised when a fresh decoder physical candidate cannot be prepared safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderCandidatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    proof_records: int
    proof_final_time_us: int


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_MAIN_NAME = "srk_saturn_main.c"
_MENU_NAME = "srk_diag_menu.c"
_CANDIDATE_DEFINE = "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1"
_CANDIDATE_MENU_LABEL = "MIDI 68K Decoder Proof"
_GATE_KEY = "midi_68k_resident_decoder_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-decoder-physical-candidate-full-build-gate.v1"
_INJECTION_MARKER = (
    "/* SRK MIDI 68K RESIDENT DECODER PHYSICAL CANDIDATE: generated seams follow. */"
)

_INSTALLER_SOURCE = "srk_saturn_midi_68k_resident_decoder_installer.c"
_INSTALLER_HEADER = "srk_saturn_midi_68k_resident_decoder_installer.h"
_PRELOAD_SOURCE = "srk_saturn_midi_68k_resident_decoder_proof_preload.c"
_PRELOAD_HEADER = "srk_saturn_midi_68k_resident_decoder_proof_preload.h"
_RUNTIME_SOURCE = "srk_saturn_midi_68k_resident_decoder_runtime.c"
_RUNTIME_HEADER = "srk_saturn_midi_68k_resident_decoder_runtime.h"
_PROOF_SOURCE = "srk_saturn_midi_68k_resident_decoder_physical_proof.c"
_PROOF_HEADER = "srk_saturn_midi_68k_resident_decoder_physical_proof.h"


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _copy_verified_inputs(
    baseline: SaturnMidi68KResidentDecoderCandidateBaseline,
    staging: Path,
) -> None:
    for entry in baseline.generated_files:
        relative = str(entry["path"])
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline.root / relative, destination)


def _inventory(root: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if path.is_file() and path.name != _MANIFEST_NAME:
            values.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return values


def _render_seams() -> dict[str, str]:
    return {
        _INSTALLER_SOURCE: render_resident_decoder_installer_source(),
        _INSTALLER_HEADER: render_resident_decoder_installer_header(),
        _PRELOAD_SOURCE: render_srk_saturn_midi_68k_resident_decoder_proof_preload_source(),
        _PRELOAD_HEADER: render_srk_saturn_midi_68k_resident_decoder_proof_preload_header(),
        _RUNTIME_SOURCE: render_resident_decoder_runtime_source(),
        _RUNTIME_HEADER: render_resident_decoder_runtime_header(),
        _PROOF_SOURCE: render_resident_decoder_proof_source(),
        _PROOF_HEADER: render_resident_decoder_proof_header(),
    }


def prepare_resident_decoder_physical_candidate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
    expected_runtime_after_sha256: str,
) -> SaturnMidi68KResidentDecoderCandidatePrepared:
    """Create a fresh callable candidate without modifying the accepted inert tree."""

    output = _canonical(output_directory)
    if output.exists():
        raise SaturnMidi68KResidentDecoderCandidatePrepareError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )

    baseline = verify_resident_decoder_inert_baseline(
        baseline_project,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_image_sha256=expected_image_sha256,
        expected_compiler_source_sha256=expected_compiler_source_sha256,
        expected_compiler_header_sha256=expected_compiler_header_sha256,
        expected_compiler_object_sha256=expected_compiler_object_sha256,
        expected_runtime_after_sha256=expected_runtime_after_sha256,
    )
    if baseline.root == output or baseline.root in output.parents:
        raise SaturnMidi68KResidentDecoderCandidatePrepareError(
            "output must not be the inert baseline or its child"
        )

    image = build_srk_saturn_midi_68k_resident_decoder_image()
    if image.sha256.lower() != str(expected_image_sha256).lower():
        raise SaturnMidi68KResidentDecoderCandidatePrepareError(
            "current decoder generator no longer matches accepted image evidence"
        )

    seams = _render_seams()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    staging = temporary / "stage"
    staging.mkdir()
    try:
        _copy_verified_inputs(baseline, staging)
        source_dir = staging / "src"
        runtime_path = source_dir / _RUNTIME_NAME
        main_path = source_dir / _MAIN_NAME
        menu_path = source_dir / _MENU_NAME
        if not runtime_path.is_file() or not main_path.is_file() or not menu_path.is_file():
            raise SaturnMidi68KResidentDecoderCandidatePrepareError(
                "inert baseline is missing runtime/main/menu source"
            )

        runtime_before = runtime_path.read_bytes()
        main_before = main_path.read_text(encoding="utf-8")
        menu_before = menu_path.read_text(encoding="utf-8")
        candidate_main = derive_resident_decoder_candidate_main(main_before).encode("utf-8")
        candidate_menu = derive_resident_decoder_candidate_menu(menu_before).encode("utf-8")
        main_path.write_bytes(candidate_main)
        menu_path.write_bytes(candidate_menu)

        for name, text in seams.items():
            (source_dir / name).write_text(text, encoding="utf-8", newline="\n")

        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentDecoderCandidatePrepareError(
                "inert runtime already contains decoder candidate injection"
            )
        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n"
        for name in (_INSTALLER_SOURCE, _PRELOAD_SOURCE, _RUNTIME_SOURCE, _PROOF_SOURCE):
            payload = seams[name].encode("utf-8")
            runtime_after += payload
            if not runtime_after.endswith(b"\n"):
                runtime_after += b"\n"
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        manifest = dict(baseline.manifest)
        policy = dict(manifest.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "midi_68k_silent_batch_candidate_bound": False,
                "midi_68k_resident_decoder_present": True,
                "midi_68k_resident_decoder_linked": True,
                "midi_68k_resident_decoder_installed": False,
                "midi_68k_resident_decoder_executed": False,
                "midi_68k_resident_decoder_candidate_bound": True,
                "midi_68k_resident_decoder_user_trigger_required": True,
                "midi_68k_resident_decoder_build_time_hardware_actions": False,
                "midi_sound_ram_writes": False,
                "midi_scsp_mmio": False,
                "midi_smpc_commands": False,
                "midi_mc68ec000_execution": False,
            }
        )
        manifest["policy"] = policy
        manifest[_GATE_KEY] = {
            "schema": _GATE_SCHEMA,
            "baseline_project": str(baseline.root),
            "baseline_manifest_sha256": baseline.manifest_sha256,
            "baseline_report_sha256": baseline.report_sha256,
            "accepted_inert_deploy_bin_sha256": baseline.deploy_bin_sha256,
            "accepted_inert_deploy_cue_sha256": baseline.deploy_cue_sha256,
            "candidate_define": _CANDIDATE_DEFINE,
            "candidate_menu_label": _CANDIDATE_MENU_LABEL,
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "poll_mode": "at-most-once-per-frame-while-running",
            "expected_read_sequence": 1,
            "expected_read_index": SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
            "expected_last_error": 0,
            "proof_records": SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
            "proof_final_time_us": SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
            "proof_covers_every_srkm_v1_opcode_once": True,
            "decoder_image_sha256": image.sha256,
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "decoder_linked": True,
            "decoder_installed_during_build": False,
            "decoder_executed_during_build": False,
            "decoder_candidate_bound": True,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active_when_deployed_and_explicitly_triggered": True,
            "seam_sha256": {
                name: _sha256_bytes(text.encode("utf-8")) for name, text in seams.items()
            },
        }
        manifest["generated_files"] = _inventory(staging)
        (staging / _MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        staging.replace(output)
        temporary.rmdir()
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return SaturnMidi68KResidentDecoderCandidatePrepared(
        baseline_root=baseline.root,
        output_root=output,
        baseline_manifest_sha256=baseline.manifest_sha256,
        baseline_report_sha256=baseline.report_sha256,
        baseline_bin_sha256=baseline.deploy_bin_sha256,
        baseline_cue_sha256=baseline.deploy_cue_sha256,
        image_sha256=image.sha256,
        candidate_main_sha256=_sha256_bytes(candidate_main),
        candidate_menu_sha256=_sha256_bytes(candidate_menu),
        runtime_after_sha256=_sha256_bytes(runtime_after),
        proof_records=SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
        proof_final_time_us=SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
    )
