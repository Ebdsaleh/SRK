from pathlib import Path
from types import SimpleNamespace

from rikai_kotoba.tools import saturn_sbl_space_spectre_native_candidate as cli


def test_native_candidate_cli_reports_sequence_playback(monkeypatch, tmp_path, capsys):
    output = tmp_path / "candidate"
    assets = SimpleNamespace(
        sequence_bank_sha256="1" * 64,
        melodic_tone_bank_sha256="2" * 64,
        drum_tone_bank_sha256="3" * 64,
        area_map_sha256="4" * 64,
        melodic_start=0x0B000,
        drum_start=0x20000,
        sequence_start=0x70000,
    )
    build = SimpleNamespace(successful=True, report_path=output / "SRK_STANDALONE_BUILD.json")
    result = SimpleNamespace(
        project_root=output,
        build=build,
        note_count=4381,
        sequence_bank_bytes=23127,
        assets=assets,
    )

    def fake_build(baseline, sequence, saturn_root, destination):
        assert Path(destination) == output
        return result

    validated = []
    monkeypatch.setattr(cli, "_validate_locked_sequence_directory", lambda path: validated.append(Path(path)))
    monkeypatch.setattr(cli, "build_saturn_sbl_native_sequence_candidate", fake_build)
    sequence = tmp_path / "sequence"
    rc = cli.main(
        [
            "--baseline", str(tmp_path / "baseline"),
            "--sequence", str(sequence),
            "--saturn-root", str(tmp_path / "Saturn-Dev"),
            "--output", str(output),
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert validated == [sequence]
    assert "Playback API         : SND_StartSeq" in captured.out
    assert "Sequence status      : SND_GetSeqStat" in captured.out
    assert "Direct MIDI streaming: NO" in captured.out
    assert "SH-2 event scheduler : NO" in captured.out
    assert "SAROO writes         : NONE" in captured.out
