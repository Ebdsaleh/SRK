"""Regression tests for the silent full-batch resident MC68EC000 image."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_STATE_ADDRESS,
    SATURN_MIDI_68K_TELEMETRY_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
    simulate_srk_saturn_midi_68k_command_engine,
)
from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_consumer import (
    SATURN_MIDI_68K_SILENT_BATCH_ERROR_COUNT,
    SATURN_MIDI_68K_SILENT_BATCH_ERROR_RECORD,
    SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS,
    SATURN_MIDI_68K_SILENT_BATCH_MAX_END,
    SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET,
    SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET,
    SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET,
    build_srk_saturn_midi_68k_silent_batch_consumer_image,
    render_srk_saturn_midi_68k_silent_batch_header,
    render_srk_saturn_midi_68k_silent_batch_source,
)
from rikai_kotoba.hardware.saturn.midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_QUEUE_ADDRESS,
    build_srk_saturn_midi_bridge_assets,
)
from rikai_kotoba.hardware.saturn.midi_mailbox import build_srk_saturn_midi_preload_image


_REPO_ROOT = Path(__file__).resolve().parents[1]

_MB_WRITE_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 8
_MB_READ_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 10
_MB_WRITE_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 12
_MB_READ_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 14
_MB_QUEUE_COUNT = SATURN_MIDI_MAILBOX_ADDRESS + 18
_MB_LAST_ERROR = SATURN_MIDI_MAILBOX_ADDRESS + 20


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    return tuple((payload[index] << 8) | payload[index + 1] for index in range(0, len(payload), 2))


def _canonical_sound_ram_words() -> dict[int, int]:
    preload = build_srk_saturn_midi_preload_image()
    memory: dict[int, int] = {}
    for index, word in enumerate(preload.mailbox_words):
        memory[SATURN_MIDI_MAILBOX_ADDRESS + index * 2] = word
    for index, word in enumerate(preload.queue_words):
        memory[SATURN_MIDI_QUEUE_ADDRESS + index * 2] = word
    return memory


def _run_reviewed_subset(words: tuple[int, ...], memory: dict[int, int], *, max_steps: int = 100000):
    """Execute only the reviewed instruction subset emitted by the generator."""

    registers = [0] * 8
    pc = 0
    z = False
    writes: list[tuple[int, int]] = []

    for _ in range(max_steps):
        opcode = words[pc]

        # The generated terminal holds are BRA.S -2.  Stop before looping.
        if opcode == 0x60FE:
            return memory, tuple(writes), pc

        if opcode & 0xF1FF == 0x3038:
            data_register = (opcode >> 9) & 7
            address = words[pc + 1]
            registers[data_register] = memory.get(address, 0) & 0xFFFF
            pc += 2
            continue

        if opcode & 0xFFF8 == 0x0C40:
            data_register = opcode & 7
            immediate = words[pc + 1]
            z = (registers[data_register] & 0xFFFF) == immediate
            pc += 2
            continue

        if opcode & 0xFFF8 == 0x0240:
            data_register = opcode & 7
            immediate = words[pc + 1]
            registers[data_register] &= immediate
            registers[data_register] &= 0xFFFF
            z = registers[data_register] == 0
            pc += 2
            continue

        if opcode == 0x31FC:
            immediate = words[pc + 1]
            address = words[pc + 2]
            memory[address] = immediate
            writes.append((address, immediate))
            pc += 3
            continue

        if opcode & 0xFFF8 == 0x31C0:
            data_register = opcode & 7
            address = words[pc + 1]
            value = registers[data_register] & 0xFFFF
            memory[address] = value
            writes.append((address, value))
            pc += 2
            continue

        condition = (opcode >> 8) & 0xF
        if opcode & 0xF000 == 0x6000 and (opcode & 0xFF) == 0:
            displacement = words[pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            take = condition == 0 or (condition == 6 and not z) or (condition == 7 and z)
            if take:
                # Bcc.W displacement is relative to the opcode address + 2,
                # i.e. the extension-word address.
                target_byte = (pc * 2 + 2) + displacement
                if target_byte & 1:
                    raise AssertionError("generated Bcc.W target is odd")
                pc = target_byte // 2
            else:
                pc += 2
            continue

        raise AssertionError(f"unexpected generated 68K opcode 0x{opcode:04X} at word {pc}")

    raise AssertionError("generated 68K image did not reach a terminal hold")


class SaturnMidi68KSilentBatchConsumerTests(unittest.TestCase):
    def test_image_geometry_is_stable_and_bounded(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        self.assertEqual(SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS, 0x00004000)
        self.assertEqual(image.expected_records, 27)
        self.assertEqual(image.queue_word_count, 108)
        self.assertEqual(len(image.words), 5066)
        self.assertEqual(image.byte_size, 10132)
        self.assertEqual(image.end_address, 0x00006794)
        self.assertLess(image.end_address, SATURN_MIDI_68K_SILENT_BATCH_MAX_END)
        self.assertEqual(image.words, build_srk_saturn_midi_68k_silent_batch_consumer_image().words)
        self.assertEqual(image.sha256, build_srk_saturn_midi_68k_silent_batch_consumer_image().sha256)

    def test_machine_image_consumes_full_canonical_batch_before_ack(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        memory, writes, _ = _run_reviewed_subset(image.words, _canonical_sound_ram_words())

        self.assertEqual(memory[_MB_READ_INDEX], SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS)
        self.assertEqual(memory[_MB_READ_SEQUENCE], memory[_MB_WRITE_SEQUENCE])
        self.assertEqual(memory[_MB_LAST_ERROR], 0)
        self.assertEqual(
            memory[SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET],
            27,
        )
        self.assertEqual(
            memory[SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET],
            27,
        )
        self.assertEqual(
            memory[SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET],
            1,
        )
        self.assertTrue(writes)

    def test_machine_image_publishes_exact_model_state(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        memory, _, _ = _run_reviewed_subset(image.words, _canonical_sound_ram_words())
        assets = build_srk_saturn_midi_bridge_assets()
        expected = simulate_srk_saturn_midi_68k_command_engine(assets.program)

        summary = pack_srk_saturn_midi_68k_state_words(expected)
        for index, word in enumerate(summary):
            self.assertEqual(memory[SATURN_MIDI_68K_STATE_ADDRESS + index * 2], word)

        controllers = _bytes_to_words(pack_srk_saturn_midi_68k_controller_bytes(expected))
        for index, word in enumerate(controllers):
            self.assertEqual(memory[SATURN_MIDI_68K_CONTROLLER_ADDRESS + index * 2], word)

        notes = _bytes_to_words(pack_srk_saturn_midi_68k_active_note_bitmap(expected))
        for index, word in enumerate(notes):
            self.assertEqual(memory[SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + index * 2], word)

    def test_corrupt_queue_record_fails_without_public_ack_or_state_ready(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        memory = _canonical_sound_ram_words()
        corrupt_record = 9
        address = SATURN_MIDI_QUEUE_ADDRESS + corrupt_record * 8 + 4
        memory[address] ^= 1

        memory, writes, _ = _run_reviewed_subset(image.words, memory)

        self.assertEqual(memory.get(_MB_READ_INDEX, 0), 0)
        self.assertEqual(memory.get(_MB_READ_SEQUENCE, 0), 0)
        self.assertEqual(memory[_MB_LAST_ERROR], SATURN_MIDI_68K_SILENT_BATCH_ERROR_RECORD)
        self.assertEqual(
            memory[SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET],
            corrupt_record,
        )
        self.assertEqual(
            memory.get(
                SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET,
                0,
            ),
            0,
        )
        self.assertFalse(any(address >= SATURN_MIDI_68K_STATE_ADDRESS and address < 0x1D00 for address, _ in writes))

    def test_wrong_batch_count_fails_before_queue_validation(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        memory = _canonical_sound_ram_words()
        memory[_MB_QUEUE_COUNT] = 26
        memory[_MB_WRITE_INDEX] = 26

        memory, _, _ = _run_reviewed_subset(image.words, memory)

        self.assertEqual(memory.get(_MB_READ_INDEX, 0), 0)
        self.assertEqual(memory[_MB_LAST_ERROR], SATURN_MIDI_68K_SILENT_BATCH_ERROR_COUNT)
        self.assertEqual(
            memory.get(
                SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET,
                0,
            ),
            0,
        )

    def test_runtime_writes_remain_below_scsp_audio_boundary(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        _, writes, _ = _run_reviewed_subset(image.words, _canonical_sound_ram_words())
        self.assertTrue(writes)
        self.assertTrue(all(0 <= address < 0x2000 for address, _ in writes))

    def test_generated_c_representation_is_deterministic_and_silent(self):
        header = render_srk_saturn_midi_68k_silent_batch_header()
        source = render_srk_saturn_midi_68k_silent_batch_source()
        self.assertIn("PROGRAM_WORD_COUNT 5066u", header)
        self.assertIn("PROGRAM_BYTE_SIZE 10132u", header)
        self.assertIn("EXPECTED_RECORDS 27u", header)
        self.assertIn("QUEUE_WORDS 108u", header)
        self.assertIn("0x3038u", source)
        self.assertIn("0x31FCu", source)
        self.assertNotIn("volatile", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x2010001F", source)
        self.assertNotIn("SNDON", source)
        self.assertNotIn("SNDOFF", source)

        module_text = (
            _REPO_ROOT
            / "src"
            / "rikai_kotoba"
            / "hardware"
            / "saturn"
            / "midi_68k_silent_batch_consumer.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("0x25B00000", module_text)
        self.assertNotIn("0x2010001F", module_text)


if __name__ == "__main__":
    unittest.main()
