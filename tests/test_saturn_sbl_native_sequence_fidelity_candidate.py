from __future__ import annotations

from hashlib import sha256

import pytest

from rikai_kotoba.hardware.saturn.sbl_native_sequence_fidelity_candidate import (
    GATE3F_DRUM_BYTES,
    GATE3F_DRUM_SHA256,
    GATE3F_MELODIC_BYTES,
    GATE3F_MELODIC_SHA256,
    SaturnSblNativeSequenceFidelityCandidateError,
    _replace_manifest_hash,
    _require_golden,
)
from rikai_kotoba.tools.saturn_sbl_space_spectre_gate3f_candidate import build_parser


def test_gate3f_golden_locks_are_exact_eridu_closure_values() -> None:
    assert GATE3F_MELODIC_BYTES == 321_140
    assert GATE3F_DRUM_BYTES == 111_786
    assert GATE3F_MELODIC_SHA256 == "2170b6145a250bf00abe915f523308ddb7377ee456ec7b01458afa2b7244e269"
    assert GATE3F_DRUM_SHA256 == "15e4eee6b37548c9181a53906a73e3f8997c414a1538f2cceed3e25e79ab382f"


def test_require_golden_rejects_any_byte_change() -> None:
    payload = b"corrected-ton"
    digest = sha256(payload).hexdigest()
    _require_golden("test", payload, digest, len(payload))
    with pytest.raises(SaturnSblNativeSequenceFidelityCandidateError):
        _require_golden("test", payload + b"!", digest, len(payload))


def test_staged_manifest_rewrites_hash_and_size() -> None:
    manifest = {
        "generated_files": [
            {"path": "cd/SRKGM.BIN", "size": 3, "sha256": "old"},
        ]
    }
    payload = b"abcdef"
    _replace_manifest_hash(manifest, "cd/SRKGM.BIN", payload)
    entry = manifest["generated_files"][0]
    assert entry["size"] == len(payload)
    assert entry["sha256"] == sha256(payload).hexdigest()


def test_staged_manifest_requires_unique_tone_entry() -> None:
    with pytest.raises(SaturnSblNativeSequenceFidelityCandidateError):
        _replace_manifest_hash({"generated_files": []}, "cd/SRKGM.BIN", b"x")


def test_gate3f_cli_is_off_card_only() -> None:
    parser = build_parser()
    destinations = {action.dest for action in parser._actions}
    assert {"failed_project", "baseline", "sequence", "saturn_root", "output"} <= destinations
    assert "soundfont" in destinations
    assert "card_root" not in destinations
    assert "apply" not in destinations
    assert "confirm" not in destinations
    assert "deploy" not in destinations
    assert "destination" not in destinations
