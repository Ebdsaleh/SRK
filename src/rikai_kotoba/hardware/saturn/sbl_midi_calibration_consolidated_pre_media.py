"""Read-only pre-media audit for the consolidated Sega SBL MIDI calibration build.

This is the media-boundary proof for the post-GATE4 consolidation. It locks the
exact Eridu-built 128-program family assets, external Sega inputs, generated
runtime/lifecycle contract, Sega Direct-MIDI one-shot setup order, standalone
build report and deployable BIN/CUE while performing no SAROO writes and no
Saturn hardware execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .sbl_midi_calibration_consolidated import _area_map
from .sbl_midi_calibration_pre_media import (
    SaturnSblMidiCalibrationPreMediaError,
    _artifact_map,
    _expect,
    _external_file,
    _file,
    _load_json,
    _require_source_anchors,
    _sha_file,
    _verify_report_manifest_binding,
)


SaturnSblMidiCalibrationConsolidatedPreMediaError = SaturnSblMidiCalibrationPreMediaError

_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_AREA_MAP = "cd/SRKMAP.BIN"
_DRIVER = "cd/SDDRVS.TSK"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"

EXPECTED_SOUND_DRIVER_SHA256 = (
    "76754e5bae4217e48d6a3c53c181033ddaab050deabda638bc41bf2f7f4906e3"
)
EXPECTED_SOUNDFONT_SHA256 = (
    "9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe"
)
EXPECTED_SEGA_SND_SHA256 = (
    "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"
)
EXPECTED_AREA_MAP_SHA256 = (
    "40530e1a0f1b147a6f87aaaa00de7593b82fbec806f291bcddc2b09d865a4605"
)
EXPECTED_MAX_FAMILY_BYTES = 185568
EXPECTED_PROGRAM_COUNT = 128
EXPECTED_FAMILY_COUNT = 16

EXPECTED_FAMILIES = (
    (0, "GMC00.BIN", tuple(range(0, 8)), 91004, "4ae4dc18cd63f4b8ebf7ebc0491882ffde8f56ff01129b47e51202be7dab6569"),
    (1, "GMC01.BIN", tuple(range(8, 16)), 131334, "25c5b1aee5a6b3c2af22d2c1e5804c11509940ad7fc5ad9be7798c19fc3a0005"),
    (2, "GMC02.BIN", tuple(range(16, 24)), 48360, "a352257bc94d1255b740022fcb04b639cde6fdfc7759bfaf6672da8fdd404f1e"),
    (3, "GMC03.BIN", tuple(range(24, 32)), 115774, "ac24a129f15cb7ab39cb34eb4ceec5dd3d8d027135a86f291ddb8d94809f5b99"),
    (4, "GMC04.BIN", tuple(range(32, 40)), 35110, "8c2ca555baec9f340d9c04cdf804078c5f40c52a96cb1b3b01113fb2d605d7c4"),
    (5, "GMC05.BIN", tuple(range(40, 48)), 160362, "8997da882d961418d894392ede57f218923c3d2845ebd4ba428d1a1dcd75ac5e"),
    (6, "GMC06.BIN", tuple(range(48, 56)), 185106, "a8f1759643c36d03feb9c9cd30d049b58c14bdab6a25413247670ab317e06a9f"),
    (7, "GMC07.BIN", tuple(range(56, 64)), 83356, "ba6b18f929be00406eafefc9ca450b2eba9a9156217a37cb4cd0589c905c736d"),
    (8, "GMC08.BIN", tuple(range(64, 72)), 86670, "50345944f7dc2d0a8ba9b5bd8eac6557429082c3e1369e399d7618c71f8334f8"),
    (9, "GMC09.BIN", tuple(range(72, 80)), 160186, "b39f4539f91717fa33c9c22177e4e124974e439818d6957cbc5778d23d54b7a8"),
    (10, "GMC10.BIN", tuple(range(80, 88)), 114708, "360075b9be19142fd9f0608da34f9aeabfc7eec4778d3346641e3452df2593ca"),
    (11, "GMC11.BIN", tuple(range(88, 96)), 156828, "bc768d084e73975333078cfb6266f3bb6378873ab79930a1b0ed9091f506ffc2"),
    (12, "GMC12.BIN", tuple(range(96, 104)), 104026, "f2b5ee3e638e27b4bc9d92c68f7a87d14d6cf22b8efdec6588f7d8eb51d59155"),
    (13, "GMC13.BIN", tuple(range(104, 112)), 83090, "b5e1021f5497c87ff11bd93a5b3b63d4b3880f9fd9e985357784000f6e01f4b8"),
    (14, "GMC14.BIN", tuple(range(112, 120)), 120318, "8214ed1150202d2fa468bb39625ffc891476487c00c51fb1da26700d3746b832"),
    (15, "GMC15.BIN", tuple(range(120, 128)), 185568, "ea7300837a5cb678d693d1888425c89c5e998eb2217116cf34f144daf6c4a88e"),
)

EXPECTED_ARTIFACTS = {
    "build/srk_diag.bin": (84416, "b92dfb585adf88f27922237e9f95d6d996cc14c893427b930ef36b92d05e2fbb"),
    "build/srk_diag.iso": (2097152, "b816b72e93c0f737e52abce7ff768e70fef6af95bd1d985754a1076ad7f96ff4"),
    "build/srk_diag.map": (69410, "cfc15377f66cdd8a17a9fd1946d3be40facfd988923bcf2fa4f2c17e1654d691"),
    "cd/0.bin": (84416, "b92dfb585adf88f27922237e9f95d6d996cc14c893427b930ef36b92d05e2fbb"),
    "cd/SRKPCM.BIN": (1040, "d4b9e26d0e3b0e54085b6169c5c0fc784ec9c3f005bcbbda96529db443c07b39"),
    _DEPLOY_BIN: (2408448, "56fc685e8df1e3f4f28806ef703bbfcc26b5bd48105a7aeae5917f7158f967ca"),
    _DEPLOY_CUE: (81, "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"),
}


def _verify_generated_inventory(root: Path, manifest: dict) -> set[str]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated manifest has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
                "generated-file inventory contains a non-object"
            )
        relative = entry.get("path")
        size = entry.get("size")
        expected_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(size, int)
            or size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
                "generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _file(root, relative, "generated consolidated input")
        _expect(path.stat().st_size, size, f"generated size {relative}")
        _expect(_sha_file(path), expected_sha.lower(), f"generated SHA-256 {relative}")

    required = {_DRIVER, _AREA_MAP, _RUNTIME, _MAIN}
    required.update(f"cd/GMC{family:02d}.BIN" for family in range(EXPECTED_FAMILY_COUNT))
    missing = required - seen
    if missing:
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "generated inventory lacks consolidated files: " + ", ".join(sorted(missing))
        )
    return seen


def _require_sega_oneshot_order(runtime: str) -> None:
    ordered = (
        "SND_MoveData((Uint16 *)srk_cal_family",
        "SND_ChgMix(0,0)",
        "SND_SetTlVl(15)",
        "srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,SRK_SBL_CAL_CHANNEL,SRK_SBL_CAL_BANK_CONTROLLER,0u)",
        "srk_cal_send(SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,(Uint8)voice,0u)",
    )
    positions = tuple(runtime.find(anchor) for anchor in ordered)
    if any(position < 0 for position in positions):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated runtime lacks the complete Sega Direct-MIDI one-shot setup"
        )
    if positions != tuple(sorted(positions)) or len(set(positions)) != len(positions):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated runtime no longer follows Sega one-shot order: "
            "MoveData -> ChgMix -> SetTlVl -> CC32 -> Program Change"
        )
    if "SND_StartSeq" in runtime:
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "Direct-MIDI calibration unexpectedly requires a sequence start"
        )


@dataclass(frozen=True)
class SaturnSblMidiCalibrationConsolidatedPreMediaReport:
    project_root: Path
    manifest_sha256: str
    build_report_sha256: str
    sound_driver_sha256: str
    soundfont_sha256: str
    sega_snd_sha256: str
    area_map_sha256: str
    family_sha256: tuple[str, ...]
    bin_sha256: str
    cue_sha256: str
    bin_bytes: int
    cue_bytes: int
    program_count: int
    family_count: int
    largest_family_bytes: int
    screen_owned_sbl_lifecycle: bool
    raw_scsp_audio_test_retained: bool
    driver_execution_telemetry: bool
    sega_oneshot_order: bool
    deployable_verified_against_iso: bool


def audit_consolidated_midi_calibration_pre_media(
    project_directory: Path | str,
) -> SaturnSblMidiCalibrationConsolidatedPreMediaReport:
    try:
        root = Path(project_directory).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            f"consolidated calibration project is unavailable: {project_directory}"
        ) from exc
    if not root.is_dir():
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            f"consolidated calibration project is not a directory: {root}"
        )

    manifest_path = _file(root, _MANIFEST, "consolidated project manifest")
    report_path = _file(root, _REPORT, "consolidated build report")
    manifest = _load_json(manifest_path, "consolidated project manifest")
    build = _load_json(report_path, "consolidated build report")

    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    _verify_generated_inventory(root, manifest)

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated manifest policy is missing"
        )
    for key, expected in {
        "sd_writes": False,
        "sbl_midi_calibration_candidate": True,
        "sbl_midi_calibration_consolidated": True,
        "gate3f_fidelity_policy": True,
        "hardware_executed_during_build": False,
        "raw_scsp_audio_callbacks_disabled": False,
        "screen_owned_sbl_lifecycle": True,
        "silent_placeholder_gm_voices": False,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")
    if policy.get("saroo_writes") not in (None, False):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated manifest permits SAROO writes"
        )

    calibration = manifest.get("sbl_midi_calibration")
    if not isinstance(calibration, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated calibration manifest record is missing"
        )
    _expect(
        calibration.get("schema"),
        "srk.saturn.sbl-midi-calibration-consolidated.v1",
        "calibration schema",
    )
    for key, expected in {
        "review_persistence_bound": False,
        "raw_scsp_audio_callbacks_disabled": False,
        "screen_owned_sbl_lifecycle": True,
        "off_card_only": True,
    }.items():
        _expect(calibration.get(key), expected, f"calibration {key}")

    direct = calibration.get("direct_midi")
    if not isinstance(direct, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated Direct-MIDI contract is missing"
        )
    for key, expected in {
        "sequence": 2,
        "priority": 0,
        "melodic_channel": 0,
        "bank_select_controller": 32,
        "loaded_bank": 0,
        "family_local_voice": True,
        "pan_controller": 10,
        "reference_note": 60,
        "reference_velocity": 100,
        "reference_pan": 64,
    }.items():
        _expect(direct.get(key), expected, f"Direct-MIDI {key}")

    telemetry = calibration.get("telemetry")
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated telemetry contract is missing"
        )
    for key, expected in {
        "driver_error_address": "0x25A00416",
        "command_history_offset_address": "0x25A0041A",
        "cpu_error_address": "0x25A00420",
        "command_history_proves_driver_execution": True,
    }.items():
        _expect(telemetry.get(key), expected, f"telemetry {key}")

    driver = _file(root, _DRIVER, "copied sound driver")
    area_map = _file(root, _AREA_MAP, "consolidated area map")
    _expect(_sha_file(driver), EXPECTED_SOUND_DRIVER_SHA256, "copied sound-driver SHA-256")
    _expect(_sha_file(area_map), EXPECTED_AREA_MAP_SHA256, "area-map SHA-256")
    _expect(area_map.read_bytes(), _area_map(EXPECTED_MAX_FAMILY_BYTES), "area-map bytes")

    _external_file(calibration.get("sound_driver"), "sound driver", EXPECTED_SOUND_DRIVER_SHA256)
    _external_file(calibration.get("soundfont"), "SoundFont", EXPECTED_SOUNDFONT_SHA256)
    sega_snd_path = _external_file(calibration.get("sega_snd"), "sega_snd.a", EXPECTED_SEGA_SND_SHA256)

    area_record = calibration.get("area_map")
    if not isinstance(area_record, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated area-map record is missing"
        )
    _expect(area_record.get("sha256"), EXPECTED_AREA_MAP_SHA256, "area-map manifest SHA-256")
    _expect(area_record.get("bytes"), 10, "area-map byte count")
    _expect(area_record.get("bank0_start"), 0xB000, "area-map bank0 start")
    _expect(area_record.get("reserved_bytes"), EXPECTED_MAX_FAMILY_BYTES, "area-map reservation")

    family_records = calibration.get("families")
    if not isinstance(family_records, list) or len(family_records) != EXPECTED_FAMILY_COUNT:
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated manifest does not contain exactly 16 GM families"
        )
    family_hashes: list[str] = []
    covered: list[int] = []
    for expected, record in zip(EXPECTED_FAMILIES, family_records):
        family, filename, programs, size, expected_sha = expected
        if not isinstance(record, dict):
            raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
                f"GM family {family} manifest record is invalid"
            )
        _expect(record.get("family"), family, f"GM family {family} id")
        _expect(record.get("filename"), filename, f"GM family {family} filename")
        _expect(tuple(record.get("programs") or ()), programs, f"GM family {family} programs")
        _expect(record.get("bytes"), size, f"GM family {family} bytes")
        _expect(record.get("sha256"), expected_sha, f"GM family {family} manifest SHA-256")
        path = _file(root, f"cd/{filename}", f"GM family {family}")
        _expect(path.stat().st_size, size, f"GM family {family} disk bytes")
        _expect(_sha_file(path), expected_sha, f"GM family {family} disk SHA-256")
        covered.extend(programs)
        family_hashes.append(expected_sha)
    _expect(tuple(covered), tuple(range(EXPECTED_PROGRAM_COUNT)), "complete GM program coverage")

    _expect(build.get("schema"), "srk.saturn.standalone-build.v1", "build-report schema")
    _expect(build.get("successful"), True, "standalone build success")
    manifest_sha = _verify_report_manifest_binding(manifest_path, build)
    build_policy = build.get("policy")
    if not isinstance(build_policy, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "build-report policy is missing"
        )
    for key, expected in {
        "shell_used": False,
        "path_mutated": False,
        "source_inputs_verified_after_build": True,
        "private_sdk_dependencies_verified_after_build": True,
        "private_sdk_dependencies_copied": False,
        "sd_writes": False,
        "commercial_image_changes": False,
    }.items():
        _expect(build_policy.get(key), expected, f"build policy {key}")

    runtime = _file(root, _RUNTIME, "consolidated runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    _require_source_anchors(
        runtime,
        (
            'GFS_Load(id,0,dst,(Sint32)bytes)',
            'static unsigned int srk_cal_begin(void *context)',
            'SND_Init(&ini);',
            'SND_ChgMap(0)',
            'SND_MoveData((Uint16 *)srk_cal_family',
            'SND_ChgMix(0,0)',
            'SND_SetTlVl(15)',
            'family=program/SRK_SBL_CAL_FAMILY_SIZE',
            'voice=program%SRK_SBL_CAL_FAMILY_SIZE',
            'SND_KD_TONE,0',
            '0x25A00416UL',
            '0x25A0041AUL',
            '0x25A00420UL',
            'history!=s->history_baseline',
            's->driver_executed=1u',
            'host->midi_persist_review=0;',
            'SND_OffAllSound()',
            'srk_saturn_audio_bind(srk_cal_host,host_state);',
        ),
        "consolidated runtime",
    )
    _require_sega_oneshot_order(runtime)

    main = _file(root, _MAIN, "consolidated main").read_text(
        encoding="utf-8", errors="strict"
    )
    _require_source_anchors(
        main,
        (
            'srk_saturn_audio_bind(&srk_host, &srk_host_state);',
            'srk_saturn_sbl_midi_calibration_runtime_bind(&srk_host',
            'srk_saturn_sbl_midi_calibration_runtime_stop',
            'srk_saturn_sbl_midi_calibration_runtime_poll',
            'SDDRV exec:',
            '68K err:',
            'Hist:',
            'Queued:',
        ),
        "consolidated main",
    )
    for forbidden in (
        'srk_host.present_audio_tone = 0;',
        'srk_host.stop_audio = 0;',
        'srk_host.read_audio_status = 0;',
        'SND_Init',
    ):
        if forbidden in main:
            raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
                f"consolidated main violates screen-owned/raw-SCSP contract: {forbidden}"
            )
    if main.count("srk_diag_app_frame(") != 1:
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "consolidated main no longer has exactly one reusable diagnostic app frame loop"
        )

    deployable = build.get("deployable")
    if not isinstance(deployable, dict):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "build report has no deployable BIN/CUE"
        )
    for key, expected in {
        "format": "cue-bin-mode1-2352",
        "bin": _DEPLOY_BIN,
        "cue": _DEPLOY_CUE,
        "verified_against_iso": True,
    }.items():
        _expect(deployable.get(key), expected, f"deployable {key}")

    artifacts = _artifact_map(build)
    for relative, (expected_size, expected_sha) in EXPECTED_ARTIFACTS.items():
        path = _file(root, relative, f"locked artifact {relative}")
        _expect(path.stat().st_size, expected_size, f"artifact size {relative}")
        _expect(_sha_file(path), expected_sha, f"artifact SHA-256 {relative}")
        record = artifacts.get(relative)
        if not isinstance(record, dict):
            raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
                f"build report lacks artifact record for {relative}"
            )
        _expect(record.get("size"), expected_size, f"report artifact size {relative}")
        _expect(record.get("sha256"), expected_sha, f"report artifact SHA-256 {relative}")

    cue_path = _file(root, _DEPLOY_CUE, "deployable CUE")
    cue_text = cue_path.read_text(encoding="ascii", errors="strict")
    if (
        'FILE "SRK-Diagnostics.bin" BINARY' not in cue_text
        or "TRACK 01 MODE1/2352" not in cue_text
    ):
        raise SaturnSblMidiCalibrationConsolidatedPreMediaError(
            "deployable CUE no longer describes the expected single MODE1/2352 BIN"
        )

    return SaturnSblMidiCalibrationConsolidatedPreMediaReport(
        project_root=root,
        manifest_sha256=manifest_sha,
        build_report_sha256=_sha_file(report_path),
        sound_driver_sha256=EXPECTED_SOUND_DRIVER_SHA256,
        soundfont_sha256=EXPECTED_SOUNDFONT_SHA256,
        sega_snd_sha256=_sha_file(sega_snd_path),
        area_map_sha256=EXPECTED_AREA_MAP_SHA256,
        family_sha256=tuple(family_hashes),
        bin_sha256=EXPECTED_ARTIFACTS[_DEPLOY_BIN][1],
        cue_sha256=EXPECTED_ARTIFACTS[_DEPLOY_CUE][1],
        bin_bytes=EXPECTED_ARTIFACTS[_DEPLOY_BIN][0],
        cue_bytes=EXPECTED_ARTIFACTS[_DEPLOY_CUE][0],
        program_count=EXPECTED_PROGRAM_COUNT,
        family_count=EXPECTED_FAMILY_COUNT,
        largest_family_bytes=EXPECTED_MAX_FAMILY_BYTES,
        screen_owned_sbl_lifecycle=True,
        raw_scsp_audio_test_retained=True,
        driver_execution_telemetry=True,
        sega_oneshot_order=True,
        deployable_verified_against_iso=True,
    )
