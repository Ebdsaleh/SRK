from pathlib import Path

from rikai_kotoba.tools import saturn_sbl_space_spectre_sequence as cli


def test_native_sequence_cli_reports_no_direct_midi_or_saroo_write(tmp_path, capsys):
    output = tmp_path / "native-sequence"
    rc = cli.main(["--output", str(output)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert "SRK Space Spectre / native Sega Saturn sequence conversion" in captured.out
    assert "Playback path        : Sega SDDRV native sequence" in captured.out
    assert "Direct MIDI streaming: NO" in captured.out
    assert "SAROO writes         : NONE" in captured.out
    assert "Notes                : 4381" in captured.out
    assert (output / "SPACESEQ.BNK").is_file()
    assert (output / "SRK_SPACE_SPECTRE_SEQUENCE.json").is_file()


def test_native_sequence_cli_refuses_existing_output(tmp_path, capsys):
    output = tmp_path / "existing"
    output.mkdir()
    rc = cli.main(["--output", str(output)])
    captured = capsys.readouterr()

    assert rc == 2
    assert "refusing overwrite" in captured.err
