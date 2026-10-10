"""Contracts for SRK's title-neutral packaged Saturn PCM payload."""

from hashlib import sha256
import unittest

from rikai_kotoba.formats.saturn.packaged_pcm import (
    PACKAGED_PCM_CHANNELS_MONO,
    PACKAGED_PCM_ENCODING_PCM16_BE,
    PACKAGED_PCM_FILENAME,
    PACKAGED_PCM_HEADER_SIZE,
    PACKAGED_PCM_LOOP_END,
    PACKAGED_PCM_LOOP_START,
    PACKAGED_PCM_MAGIC,
    PACKAGED_PCM_SAMPLE_COUNT,
    PACKAGED_PCM_VERSION,
    SaturnPackagedPCMError,
    build_deterministic_packaged_pcm,
    parse_packaged_pcm,
)


class SaturnPackagedPCMTests(unittest.TestCase):
    def test_deterministic_payload_has_fixed_self_describing_contract(self):
        first = build_deterministic_packaged_pcm()
        second = build_deterministic_packaged_pcm()
        parsed = parse_packaged_pcm(first)

        self.assertEqual(PACKAGED_PCM_FILENAME, "SRKPCM.BIN")
        self.assertEqual(first, second)
        self.assertEqual(first[0:4], PACKAGED_PCM_MAGIC)
        self.assertEqual(first[4], PACKAGED_PCM_VERSION)
        self.assertEqual(first[5], PACKAGED_PCM_ENCODING_PCM16_BE)
        self.assertEqual(first[6], PACKAGED_PCM_CHANNELS_MONO)
        self.assertEqual(first[7], 0)
        self.assertEqual(
            len(first),
            PACKAGED_PCM_HEADER_SIZE + PACKAGED_PCM_SAMPLE_COUNT * 2,
        )
        self.assertEqual(parsed.sample_count, PACKAGED_PCM_SAMPLE_COUNT)
        self.assertEqual(parsed.loop_start, PACKAGED_PCM_LOOP_START)
        self.assertEqual(parsed.loop_end, PACKAGED_PCM_LOOP_END)
        self.assertEqual(len(parsed.samples), PACKAGED_PCM_SAMPLE_COUNT)
        self.assertEqual(parsed.samples[0], 0)
        self.assertEqual(parsed.samples[-1], 0)
        self.assertEqual(sha256(first).hexdigest(), sha256(second).hexdigest())

    def test_parser_rejects_tampering_and_unsupported_metadata(self):
        payload = bytearray(build_deterministic_packaged_pcm())

        broken_magic = bytearray(payload)
        broken_magic[0] = ord("X")
        with self.assertRaises(SaturnPackagedPCMError):
            parse_packaged_pcm(bytes(broken_magic))

        broken_reserved = bytearray(payload)
        broken_reserved[7] = 1
        with self.assertRaises(SaturnPackagedPCMError):
            parse_packaged_pcm(bytes(broken_reserved))

        with self.assertRaises(SaturnPackagedPCMError):
            parse_packaged_pcm(bytes(payload[:-2]))


if __name__ == "__main__":
    unittest.main()
