from __future__ import annotations

import json

import pytest

from rikai_kotoba.hardware.saturn.sbl_native_sequence_fidelity_pre_media import (
    EXPECTED_AREA_MAP_SHA256,
    EXPECTED_DRUM_START,
    EXPECTED_SEQUENCE_START,
    SaturnSblNativeSequenceFidelityPreMediaError,
    _sha_file,
    _verify_report_manifest_binding,
)
from rikai_kotoba.tools.saturn_sbl_space_spectre_gate3f_pre_media import _parser


def test_gate3f_corrected_sizes_lock_sound_ram_layout_and_area_map() -> None:
    assert EXPECTED_DRUM_START == 0x59674
    assert EXPECTED_SEQUENCE_START == 0x74B20
    assert EXPECTED_AREA_MAP_SHA256 == (
        "cd21001f424860f7aaa3fb6c49b7a00c31ea59d225a3568a308ca7524d4b8d6f"
    )


def test_pre_media_requires_build_report_to_hash_final_manifest(tmp_path) -> None:
    manifest = tmp_path / "SRK_STANDALONE_PROJECT.json"
    manifest.write_text(json.dumps({"schema": "x"}) + "\n", encoding="utf-8")
    actual = _sha_file(manifest)
    assert _verify_report_manifest_binding(
        manifest, {"project_manifest_sha256": actual}
    ) == actual
    with pytest.raises(SaturnSblNativeSequenceFidelityPreMediaError):
        _verify_report_manifest_binding(
            manifest, {"project_manifest_sha256": "0" * 64}
        )


def test_gate3f_pre_media_cli_has_no_media_or_mutation_surface() -> None:
    parser = _parser()
    destinations = {action.dest for action in parser._actions}
    assert "project" in destinations
    for forbidden in (
        "card_root",
        "destination",
        "destination_name",
        "apply",
        "confirm",
        "deploy",
        "output",
    ):
        assert forbidden not in destinations
