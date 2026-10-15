from __future__ import annotations

from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn.sound_sdk_probe import (
    SaturnSoundSdkProbeError,
    inspect_saturn_sound_sdk,
)


def test_sound_sdk_probe_reports_exact_installed_evidence_without_writing(tmp_path: Path) -> None:
    root = tmp_path / "Saturn-Dev"
    include = root / "SBL_601" / "SEGALIB" / "INCLUDE"
    lib = root / "SBL_601" / "SEGALIB" / "LIB_ELF"
    sample = root / "SBL_601" / "SEGASMP" / "SND" / "SMPSND1"
    include.mkdir(parents=True)
    lib.mkdir(parents=True)
    sample.mkdir(parents=True)

    (include / "SEGA_SND.H").write_text(
        "void SND_StartSeq(int seq);\n"
        "void SND_StopSeq(int seq);\n"
        "void SND_SetToneBank(int bank);\n"
        "void SND_StartPcm(void);\n",
        encoding="ascii",
    )
    (include / "SEGA_CDC.H").write_text(
        "void CDC_CdPlay(void);\nvoid CDC_CdStop(void);\n",
        encoding="ascii",
    )
    (sample / "MAIN.C").write_text(
        "SND_StartSeq(0);\nSND_SetToneBank(1);\nCDC_CdPlay();\n",
        encoding="ascii",
    )
    (lib / "sega_snd.a").write_bytes(b"fake-snd-library")
    (lib / "SEGA_CDC.A").write_bytes(b"fake-cdc-library")

    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    result = inspect_saturn_sound_sdk(root)
    after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))

    assert before == after
    assert result.saturn_root == root.resolve()
    assert any(path.name == "SEGA_SND.H" for path in result.snd_headers)
    assert any(path.name == "SEGA_CDC.H" for path in result.snd_headers)
    assert {artifact.path.name.casefold() for artifact in result.snd_libraries} == {
        "sega_snd.a",
        "sega_cdc.a",
    }
    assert sample.resolve() in result.sound_samples
    assert any("SND_StartSeq" in match.line for match in result.sequence_matches)
    assert any("SND_SetToneBank" in match.line for match in result.bank_matches)
    assert any("SND_StartPcm" in match.line for match in result.pcm_matches)
    assert any("CDC_CdPlay" in match.line for match in result.cdda_matches)


def test_sound_sdk_probe_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(SaturnSoundSdkProbeError):
        inspect_saturn_sound_sdk(tmp_path / "missing")


def test_sound_sdk_probe_rejects_nonpositive_match_limit(tmp_path: Path) -> None:
    root = tmp_path / "Saturn-Dev"
    root.mkdir()
    with pytest.raises(SaturnSoundSdkProbeError):
        inspect_saturn_sound_sdk(root, match_limit=0)
