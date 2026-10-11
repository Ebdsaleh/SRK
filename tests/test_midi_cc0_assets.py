"""Integrity gates for the third-party CC0 MIDI source corpus.

These tests deliberately prove source provenance only.  They do not imply that
SRK's current parser/driver already supports every event found in the corpus.
Compatibility is a separate engineering gate.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest
import zipfile


_ROOT = Path(__file__).resolve().parents[1]
_DOUBLE_IMPACT = _ROOT / "assets/midi/cc0/double-impact/dbimmidi-oga-mid.zip"
_TOWN_THEME = _ROOT / "assets/midi/cc0/melody-town-theme/Melody Town Theme.mid"

_DOUBLE_IMPACT_SHA256 = "c665dd930726d25305f8c8e104a235399a04a04cf50d2f3eda251dd7be8d658c"
_TOWN_THEME_SHA256 = "9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041"

_DOUBLE_IMPACT_MEMBERS = {
    "midis/E1M2, E4M3 - Matzu - Space Spectre.mid": (
        36680,
        "984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01",
    ),
    "midis/E1M3, E4M2 - R0rque - Fight Harder...  To Obtain A Better Victory!.mid": (
        60593,
        "2bfe003662d065f21d424441cb2beb1ec767f40c2c08b77c7b27e2c0f090feb8",
    ),
    "midis/E1M4, E4M4 - continuum.mid - Deliberate Concealment.mid": (
        18444,
        "3a64c328f79fcdc61b725c91cc515db4a8723b177c4b82d46e775cc52884a5e8",
    ),
    "midis/E1M5, E4M5 - Korp - Main Code.mid": (
        74604,
        "cefe563e1035d06b2710b0cf71d7fbb8f4bfa60c19a60cddaa801ab01fc3f6db",
    ),
    "midis/E1M6, E4M6 - ZeMystic - Andromeda.mid": (
        22199,
        "c9c1409062221a4784b27607f804c406200b362fbe54dc822937d05690fd728e",
    ),
    "midis/E1M7, E4M7 - Korp - Ambiguity.mid": (
        58512,
        "2b1a3569765292e7ddb0d2f9bac181ec00027139a8d642cd4f2abb453c3767ea",
    ),
    "midis/E1M8, E4M8 - continuum.mid -  Vs. The Assault Quindecapod.mid": (
        17398,
        "1f12801b85594de730bdc1c7043f3de22ad0ddaa9955de4dbfb4d62a99b89458",
    ),
    "midis/E1M9, E4M9 - continuum.mid - The Deepest Secrets.mid": (
        13157,
        "10e4988a40ad1a7c0ae21680c251683c398dd80ae790477f0e0e68db980ef69b",
    ),
    "midis/E4M1 - continuum.mid - Liberate the Stars.mid": (
        18529,
        "48ad457f927172c3570777af6ef9135c1b41b53a04a493680d7d6be10f0780af",
    ),
    "midis/INTER - Korp - Resprenselessness.mid": (
        76766,
        "66460ef416f6d97ddbfc13ecd2b9cf5fa1c499a54b4e6f88310ec318e3d7b64b",
    ),
    "midis/TITLE - continuum.mid - Triple Impact.mid": (
        815,
        "d309c64f2e75ed51096223aa4b8030eaf233ae55301894416abee67c37f87dcc",
    ),
}


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


class MidiCc0AssetIntegrityTests(unittest.TestCase):
    def test_supplied_source_files_are_byte_exact(self):
        double_impact = _DOUBLE_IMPACT.read_bytes()
        town_theme = _TOWN_THEME.read_bytes()

        self.assertEqual(len(double_impact), 45337)
        self.assertEqual(_sha(double_impact), _DOUBLE_IMPACT_SHA256)
        self.assertEqual(len(town_theme), 1333)
        self.assertEqual(_sha(town_theme), _TOWN_THEME_SHA256)
        self.assertEqual(town_theme[:4], b"MThd")

    def test_double_impact_archive_has_only_the_expected_hash_locked_midis(self):
        with zipfile.ZipFile(_DOUBLE_IMPACT) as archive:
            files = {
                info.filename
                for info in archive.infolist()
                if not info.is_dir()
            }
            self.assertEqual(files, set(_DOUBLE_IMPACT_MEMBERS))

            for filename, (expected_size, expected_sha) in _DOUBLE_IMPACT_MEMBERS.items():
                with self.subTest(filename=filename):
                    data = archive.read(filename)
                    self.assertEqual(len(data), expected_size)
                    self.assertEqual(_sha(data), expected_sha)
                    self.assertEqual(data[:4], b"MThd")


if __name__ == "__main__":
    unittest.main()
