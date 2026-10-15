from pathlib import Path
import struct

from rikai_kotoba.hardware.saturn.sbl_official_tone_discovery import (
    discover_official_tone_candidates,
)
from rikai_kotoba.tools.saturn_sbl_official_tone_discovery import build_parser


def _scspbin(voices: int) -> bytes:
    assert 1 <= voices <= 128
    header_size = 8 + voices * 2
    mixer = header_size
    velocity = mixer + 18
    peg = velocity + 10
    plfo = peg + 10
    voice_start = plfo + 4
    voice_bytes = 4 + 0x20
    total = voice_start + voices * voice_bytes + 64
    payload = bytearray(total)
    struct.pack_into(">HHHH", payload, 0, mixer, velocity, peg, plfo)
    for index in range(voices):
        off = voice_start + index * voice_bytes
        struct.pack_into(">H", payload, 8 + 2 * index, off)
        payload[off : off + 4] = bytes((2, 0, 0, 0))
        payload[off + 4] = 0
        payload[off + 5] = 127
        sample_address = total - 64
        payload[off + 6 : off + 10] = sample_address.to_bytes(4, "big")
    return bytes(payload)


def test_discovery_prioritises_128_voice_gm_candidate(tmp_path):
    gm_dir = tmp_path / "DTS" / "SOUND" / "TONE BANKS"
    gm_dir.mkdir(parents=True)
    gm = gm_dir / "InVision General MIDI.bin"
    gm.write_bytes(_scspbin(128))

    sample_dir = tmp_path / "SAMPLES"
    sample_dir.mkdir()
    sample = sample_dir / "BOOTTONE.BIN"
    sample.write_bytes(_scspbin(4))

    candidates = discover_official_tone_candidates(tmp_path)

    assert candidates[0].path == gm.resolve()
    assert candidates[0].voice_count == 128
    assert "128-voices" in candidates[0].reasons
    assert any(item.path == sample.resolve() and item.voice_count == 4 for item in candidates)


def test_discovery_does_not_claim_arbitrary_bin_is_scspbin(tmp_path):
    arbitrary = tmp_path / "random.bin"
    arbitrary.write_bytes(b"not a Saturn tone bank" * 20)

    candidates = discover_official_tone_candidates(tmp_path)

    matching = [item for item in candidates if item.path == arbitrary.resolve()]
    assert matching
    assert matching[0].structurally_valid is False
    assert matching[0].voice_count is None


def test_discovery_cli_is_read_only_root_and_limit():
    args = build_parser().parse_args(
        ["--saturn-root", "Saturn-Dev", "--limit", "25"]
    )
    assert args.saturn_root == Path("Saturn-Dev")
    assert args.limit == 25
