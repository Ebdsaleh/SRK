"""Fresh off-card full-build gate for R26 Double Impact / Space Spectre.

The baseline is the exact physically accepted R24 real-song candidate. R26 is
layered beside that immutable baseline: a validated 16-slot resident image, a
287-batch Space Spectre producer and an R26 physical proof that waits for final
release ownership to drain before PASS. The gate performs host build work only;
it never accesses Saturn hardware or writes SAROO media.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile
from . import midi_68k_r25_rr_calibration_full_build_gate as _r25_gate
from .midi_68k_r26_double_impact import SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256, build_srk_saturn_midi_68k_r26_space_spectre_profile
from .midi_68k_r26_physical_candidate import derive_r26_double_impact_candidate_main, derive_r26_double_impact_candidate_menu, render_srk_saturn_midi_68k_r26_physical_proof_header, render_srk_saturn_midi_68k_r26_physical_proof_source
from .midi_68k_r26_player import render_saturn_midi_68k_r26_player_header, render_saturn_midi_68k_r26_player_source
from .midi_68k_r26_resident_audio_service import build_srk_saturn_midi_68k_r26_resident_audio_service_image, render_srk_saturn_midi_68k_r26_resident_audio_service_header, render_srk_saturn_midi_68k_r26_resident_audio_service_source
from .midi_68k_r26_voice_header import render_srk_saturn_midi_68k_r26_voice_header
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project

class SaturnMidi68KR26PhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the accepted R24 -> R26 physical candidate chain is not exact."""

@dataclass(frozen=True)
class SaturnMidi68KR26PhysicalCandidatePrepared:
    baseline_root: Path
    output_root: Path
    repository_root: Path
    release_rate: int
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    source_midi_sha256: str
    record_count: int
    batch_count: int
    duration_us: int
    note_on_count: int
    note_off_count: int
    raw_peak_polyphony: int
    release_steal_count: int
    resident_image_sha256: str
    resident_source_sha256: str
    resident_header_sha256: str
    voice_header_sha256: str
    player_source_sha256: str
    player_header_sha256: str
    proof_source_sha256: str
    proof_header_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str

@dataclass(frozen=True)
class SaturnMidi68KR26PhysicalCandidateFullBuildResult:
    prepared: SaturnMidi68KR26PhysicalCandidatePrepared
    build: SaturnStandaloneBuildResult
_MANIFEST = 'SRK_STANDALONE_PROJECT.json'
_RUNTIME = 'src/srk_saturn_runtime.c'
_MAIN = 'src/srk_saturn_main.c'
_MENU = 'src/srk_diag_menu.c'
_R26_AUDIO_SOURCE = 'src/srk_saturn_midi_68k_r26_resident_audio_service.c'
_R26_AUDIO_HEADER = 'src/srk_saturn_midi_68k_r26_resident_audio_service.h'
_R26_VOICE_HEADER = 'src/srk_saturn_midi_68k_r26_voice_state.h'
_R26_PLAYER_SOURCE = 'src/srk_saturn_midi_68k_r26_player.c'
_R26_PLAYER_HEADER = 'src/srk_saturn_midi_68k_r26_player.h'
_R26_PROOF_SOURCE = 'src/srk_saturn_midi_68k_r26_physical_proof.c'
_R26_PROOF_HEADER = 'src/srk_saturn_midi_68k_r26_physical_proof.h'
_GATE_KEY = 'midi_68k_r26_double_impact_physical_candidate_full_build_gate'
_GATE_SCHEMA = 'srk.saturn.midi-68k-r26-double-impact-physical-candidate-full-build-gate.v1'
_MARKER = '/* SRK MIDI 68K R26 DOUBLE IMPACT PHYSICAL CANDIDATE: generated sources follow. */'
ACCEPTED_R26_RELEASE_RATE = 16
ACCEPTED_R26_IMAGE_SHA256 = '7bcc139b2a689f77f03de79c0efae5e018e3584bfe15826baafa09c7aef32b40'
ACCEPTED_R26_IMAGE_WORDS = 31685
ACCEPTED_R26_IMAGE_BYTES = 63370
ACCEPTED_R26_RECORDS = 9154
ACCEPTED_R26_BATCHES = 287
ACCEPTED_R26_DURATION_US = 148093750
ACCEPTED_R26_NOTE_ON = 4381
ACCEPTED_R26_NOTE_OFF = 4381
ACCEPTED_R26_RAW_PEAK = 10
ACCEPTED_R26_PEAK_OWNED = 16
ACCEPTED_R26_RELEASE_STEALS = 12
ACCEPTED_R26_BUSY = 0

def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)

def _sha_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()

def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _inventory(root: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for path in sorted(root.rglob('*'), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.name == _MANIFEST:
            continue
        relative = path.relative_to(root).as_posix()
        if relative == 'SRK_STANDALONE_BUILD.json' or relative.startswith('build/'):
            continue
        values.append({'path': relative, 'size': path.stat().st_size, 'sha256': _sha_file(path)})
    return values

def _validate_profile(repository_root: Path):
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(repository_root)
    exact = {'source SHA': profile.member_sha256 == SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256, 'records': profile.record_count == ACCEPTED_R26_RECORDS, 'batches': profile.batch_count == ACCEPTED_R26_BATCHES, 'duration': profile.duration_us == ACCEPTED_R26_DURATION_US, 'Note On': profile.note_on_count == ACCEPTED_R26_NOTE_ON, 'Note Off': profile.note_off_count == ACCEPTED_R26_NOTE_OFF, 'raw peak': profile.raw_peak_polyphony == ACCEPTED_R26_RAW_PEAK, 'peak owned': profile.capacity.peak_owned == ACCEPTED_R26_PEAK_OWNED, 'release steals': profile.capacity.release_steal_count == ACCEPTED_R26_RELEASE_STEALS, 'busy allocations': profile.capacity.busy_count == ACCEPTED_R26_BUSY, 'final held': profile.capacity.final_held == 0, 'final releasing': profile.capacity.final_releasing == 0}
    failed = [label for label, passed in exact.items() if not passed]
    if failed:
        raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError('R26 Space Spectre profile changed: ' + ', '.join(failed))
    return profile

def prepare_saturn_midi_68k_r26_physical_candidate(baseline_project: os.PathLike[str] | str, repository_root: os.PathLike[str] | str, output_directory: os.PathLike[str] | str, *, release_rate: int=ACCEPTED_R26_RELEASE_RATE) -> SaturnMidi68KR26PhysicalCandidatePrepared:
    baseline = _canonical(baseline_project)
    repo = _canonical(repository_root)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError(f'accepted R24 physical baseline is not a directory: {baseline}')
    if not repo.is_dir():
        raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError(f'SRK repository root is not a directory: {repo}')
    if output.exists():
        raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError(f'output directory already exists; refusing to merge or overwrite: {output}')
    if release_rate != ACCEPTED_R26_RELEASE_RATE:
        raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError('R26 physical candidate must use the Eridu-validated provisional RR16 source engine')
    manifest, generated = _r25_gate._verify_r24_baseline(baseline)
    profile = _validate_profile(repo)
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(release_rate=release_rate)
    if image.sha256 != ACCEPTED_R26_IMAGE_SHA256 or image.word_count != ACCEPTED_R26_IMAGE_WORDS or image.byte_size != ACCEPTED_R26_IMAGE_BYTES:
        raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError('R26 resident image no longer matches accepted Eridu source-engine evidence')
    rendered = {_R26_AUDIO_SOURCE: render_srk_saturn_midi_68k_r26_resident_audio_service_source(release_rate=release_rate), _R26_AUDIO_HEADER: render_srk_saturn_midi_68k_r26_resident_audio_service_header(release_rate=release_rate), _R26_VOICE_HEADER: render_srk_saturn_midi_68k_r26_voice_header(), _R26_PLAYER_SOURCE: render_saturn_midi_68k_r26_player_source(profile.program), _R26_PLAYER_HEADER: render_saturn_midi_68k_r26_player_header(), _R26_PROOF_SOURCE: render_srk_saturn_midi_68k_r26_physical_proof_source(profile, release_rate=release_rate), _R26_PROOF_HEADER: render_srk_saturn_midi_68k_r26_physical_proof_header()}
    blobs = {name: text.encode('utf-8') for name, text in rendered.items()}
    hashes = {name: _sha_bytes(data) for name, data in blobs.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f'.{output.name}.', dir=str(output.parent)))
    staging = temporary / 'stage'
    staging.mkdir()
    try:
        for entry in generated:
            relative = str(entry['path'])
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(baseline / relative, destination)
        main_path = staging / _MAIN
        menu_path = staging / _MENU
        runtime_path = staging / _RUNTIME
        runtime_before = runtime_path.read_bytes()
        if _sha_bytes(runtime_before) != _r25_gate.ACCEPTED_R24_RUNTIME_SHA256:
            raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError('accepted R24 runtime changed during fresh staging')
        candidate_main = derive_r26_double_impact_candidate_main(main_path.read_text(encoding='utf-8')).encode('utf-8')
        candidate_menu = derive_r26_double_impact_candidate_menu(menu_path.read_text(encoding='utf-8')).encode('utf-8')
        main_path.write_bytes(candidate_main)
        menu_path.write_bytes(candidate_menu)
        for relative, data in blobs.items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        marker = _MARKER.encode('ascii')
        if marker in runtime_before:
            raise SaturnMidi68KR26PhysicalCandidateFullBuildGateError('accepted R24 runtime already contains R26 injection')
        runtime_after = runtime_before
        if not runtime_after.endswith(b'\n'):
            runtime_after += b'\n'
        runtime_after += b'\n' + marker + b'\n'
        for relative in (_R26_AUDIO_SOURCE, _R26_PLAYER_SOURCE, _R26_PROOF_SOURCE):
            runtime_after += blobs[relative]
            if not runtime_after.endswith(b'\n'):
                runtime_after += b'\n'
            runtime_after += b'\n'
        runtime_path.write_bytes(runtime_after)
        candidate = dict(manifest)
        policy = dict(candidate.get('policy') or {})
        policy.update({'sd_writes': False, 'midi_68k_r24_physical_baseline_preserved': True, 'midi_68k_r26_double_impact_present': True, 'midi_68k_r26_double_impact_bound': True, 'midi_68k_r26_resident_installed_during_build': False, 'midi_68k_r26_resident_executed_during_build': False, 'midi_68k_r26_frt_invoked_during_build': False, 'midi_68k_r26_build_time_hardware_io': False, 'midi_68k_r26_production_rr_selected': False})
        candidate['policy'] = policy
        candidate[_GATE_KEY] = {'schema': _GATE_SCHEMA, 'baseline_project': str(baseline), 'baseline_manifest_sha256': _r25_gate.ACCEPTED_R24_MANIFEST_SHA256, 'baseline_report_sha256': _r25_gate.ACCEPTED_R24_REPORT_SHA256, 'baseline_deploy_bin_sha256': _r25_gate.ACCEPTED_R24_BIN_SHA256, 'baseline_deploy_cue_sha256': _r25_gate.ACCEPTED_R24_CUE_SHA256, 'source_member': profile.member_name, 'source_midi_sha256': profile.member_sha256, 'record_count': profile.record_count, 'batch_count': profile.batch_count, 'last_batch_records': profile.record_count - (profile.batch_count - 1) * 32, 'duration_us': profile.duration_us, 'note_on_count': profile.note_on_count, 'note_off_count': profile.note_off_count, 'raw_peak_polyphony': profile.raw_peak_polyphony, 'r25_tail_peak_owned': profile.capacity.peak_owned, 'release_tail_steals': profile.capacity.release_steal_count, 'busy_allocations': profile.capacity.busy_count, 'release_rate': release_rate, 'release_rate_status': 'PROVISIONAL-R25-CALIBRATION-VALUE-NOT-PRODUCTION-SELECTION', 'resident_image_sha256': image.sha256, 'resident_image_words': image.word_count, 'resident_image_bytes': image.byte_size, 'resident_source_sha256': hashes[_R26_AUDIO_SOURCE], 'resident_header_sha256': hashes[_R26_AUDIO_HEADER], 'voice_header_sha256': hashes[_R26_VOICE_HEADER], 'player_source_sha256': hashes[_R26_PLAYER_SOURCE], 'player_header_sha256': hashes[_R26_PLAYER_HEADER], 'proof_source_sha256': hashes[_R26_PROOF_SOURCE], 'proof_header_sha256': hashes[_R26_PROOF_HEADER], 'candidate_main_sha256': _sha_bytes(candidate_main), 'candidate_menu_sha256': _sha_bytes(candidate_menu), 'runtime_before_sha256': _sha_bytes(runtime_before), 'runtime_after_sha256': _sha_bytes(runtime_after), 'candidate_define': '#define SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE 1', 'candidate_menu_label': 'MIDI R26 Space Spectre', 'trigger_button': 'A', 'trigger_requires_release_after_screen_entry': True, 'clock_backend': 'accepted-r24-sh2-frt-div128-runtime-vdp2-selection', 'final_release_drain_required_before_pass': True, 'frt_original_tcr_restored_on_terminal_path': True, 'resident_installed_during_build': False, 'resident_executed_during_build': False, 'frt_invoked_during_build': False, 'scsp_mmio_during_build': False, 'sound_ram_writes_during_build': False, 'build_time_hardware_io': False, 'saroo_write': False, 'off_card_only': True, 'behaviorally_active_when_deployed_and_explicitly_triggered': True}
        candidate['generated_files'] = _inventory(staging)
        (staging / _MANIFEST).write_text(json.dumps(candidate, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
        staging.replace(output)
        temporary.rmdir()
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return SaturnMidi68KR26PhysicalCandidatePrepared(baseline_root=baseline, output_root=output, repository_root=repo, release_rate=release_rate, baseline_manifest_sha256=_r25_gate.ACCEPTED_R24_MANIFEST_SHA256, baseline_report_sha256=_r25_gate.ACCEPTED_R24_REPORT_SHA256, baseline_bin_sha256=_r25_gate.ACCEPTED_R24_BIN_SHA256, baseline_cue_sha256=_r25_gate.ACCEPTED_R24_CUE_SHA256, source_midi_sha256=profile.member_sha256, record_count=profile.record_count, batch_count=profile.batch_count, duration_us=profile.duration_us, note_on_count=profile.note_on_count, note_off_count=profile.note_off_count, raw_peak_polyphony=profile.raw_peak_polyphony, release_steal_count=profile.capacity.release_steal_count, resident_image_sha256=image.sha256, resident_source_sha256=hashes[_R26_AUDIO_SOURCE], resident_header_sha256=hashes[_R26_AUDIO_HEADER], voice_header_sha256=hashes[_R26_VOICE_HEADER], player_source_sha256=hashes[_R26_PLAYER_SOURCE], player_header_sha256=hashes[_R26_PLAYER_HEADER], proof_source_sha256=hashes[_R26_PROOF_SOURCE], proof_header_sha256=hashes[_R26_PROOF_HEADER], candidate_main_sha256=_sha_bytes(candidate_main), candidate_menu_sha256=_sha_bytes(candidate_menu), runtime_before_sha256=_sha_bytes(runtime_before), runtime_after_sha256=_sha_bytes(runtime_after))

def run_saturn_midi_68k_r26_physical_candidate_full_build_gate(baseline_project: os.PathLike[str] | str, repository_root: os.PathLike[str] | str, output_directory: os.PathLike[str] | str, *, release_rate: int=ACCEPTED_R26_RELEASE_RATE) -> SaturnMidi68KR26PhysicalCandidateFullBuildResult:
    prepared = prepare_saturn_midi_68k_r26_physical_candidate(baseline_project, repository_root, output_directory, release_rate=release_rate)
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KR26PhysicalCandidateFullBuildResult(prepared=prepared, build=build)
