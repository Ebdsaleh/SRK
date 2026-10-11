"""Regression tests for the post-R19 general silent MC68EC000 decoder core."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_command_engine import SATURN_MIDI_68K_TELEMETRY_ADDRESS
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import (
    SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_CONTRACT,
    SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_COUNT,
    SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_EMPTY,
    SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_RECORD,
    SATURN_MIDI_68K_RESIDENT_DECODER_MAX_END,
    SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS,
    SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET,
    SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET,
    SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET,
    SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_PROCESSED_OFFSET,
    SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_READY_OFFSET,
    build_srk_saturn_midi_68k_resident_decoder_image,
    render_srk_saturn_midi_68k_resident_decoder_header,
    render_srk_saturn_midi_68k_resident_decoder_source,
)
from rikai_kotoba.hardware.saturn.midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_QUEUE_ADDRESS,
    build_srk_saturn_midi_bridge_assets,
)
from rikai_kotoba.hardware.saturn.midi_mailbox import (
    build_saturn_midi_mailbox_words,
    pack_saturn_midi_queue_words,
)
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]

_MB_WRITE_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 8
_MB_READ_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 10
_MB_WRITE_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 12
_MB_READ_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 14
_MB_QUEUE_COUNT = SATURN_MIDI_MAILBOX_ADDRESS + 18
_MB_LAST_ERROR = SATURN_MIDI_MAILBOX_ADDRESS + 20


def _sound_ram_words(program: SaturnMidiProgram) -> dict[int, int]:
    mailbox = build_saturn_midi_mailbox_words(program)
    queue = pack_saturn_midi_queue_words(program)
    memory: dict[int, int] = {}
    for index, word in enumerate(mailbox):
        memory[SATURN_MIDI_MAILBOX_ADDRESS + index * 2] = word
    for index, word in enumerate(queue):
        memory[SATURN_MIDI_QUEUE_ADDRESS + index * 2] = word
    return memory


def _one_record_program() -> SaturnMidiProgram:
    return SaturnMidiProgram(
        records=(SaturnMidiRecord(1234, SaturnMidiOpcode.NOTE_ON, 15, 127, 1),),
        duration_us=1234,
    )


def _max_record_program() -> SaturnMidiProgram:
    records = tuple(
        SaturnMidiRecord(
            time_us=index * 1000,
            opcode=SaturnMidiOpcode((index % 7) + 1),
            channel=index % 16,
            data0=(index * 3) & 0x7F,
            data1=(index * 5) & 0x7F,
        )
        for index in range(SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS)
    )
    return SaturnMidiProgram(records=records, duration_us=records[-1].time_us)


def _run_reviewed_subset(
    words: tuple[int, ...],
    memory: dict[int, int],
    *,
    max_steps: int = 100000,
):
    """Execute only the instruction subset emitted by the decoder generator."""

    data = [0] * 8
    address = [0] * 8
    pc = 0
    z = False
    c = False
    writes: list[tuple[int, int]] = []
    reads: list[int] = []

    def set_cmp_flags(destination: int, source: int) -> None:
        nonlocal z, c
        destination &= 0xFFFF
        source &= 0xFFFF
        z = destination == source
        c = destination < source

    for _ in range(max_steps):
        opcode = words[pc]

        if opcode == 0x60FE:
            return memory, tuple(writes), tuple(reads), pc

        if opcode & 0xF1FF == 0x3038:
            register = (opcode >> 9) & 7
            absolute = words[pc + 1]
            reads.append(absolute)
            data[register] = memory.get(absolute, 0) & 0xFFFF
            z = data[register] == 0
            c = False
            pc += 2
            continue

        if opcode & 0xF1FF == 0x303C:
            register = (opcode >> 9) & 7
            data[register] = words[pc + 1] & 0xFFFF
            z = data[register] == 0
            c = False
            pc += 2
            continue

        if opcode == 0x41F8:
            absolute = words[pc + 1]
            address[0] = absolute
            pc += 2
            continue

        if opcode & 0xF1FF == 0x3018:
            register = (opcode >> 9) & 7
            absolute = address[0]
            reads.append(absolute)
            data[register] = memory.get(absolute, 0) & 0xFFFF
            address[0] = (address[0] + 2) & 0xFFFFFFFF
            z = data[register] == 0
            c = False
            pc += 1
            continue

        if opcode & 0xF1F8 == 0x3000:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            data[destination] = data[source] & 0xFFFF
            z = data[destination] == 0
            c = False
            pc += 1
            continue

        if opcode & 0xFFF8 == 0x0C40:
            register = opcode & 7
            immediate = words[pc + 1]
            set_cmp_flags(data[register], immediate)
            pc += 2
            continue

        if opcode & 0xF1F8 == 0xB040:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            set_cmp_flags(data[destination], data[source])
            pc += 1
            continue

        if opcode & 0xFFF8 == 0x0240:
            register = opcode & 7
            immediate = words[pc + 1]
            data[register] &= immediate
            data[register] &= 0xFFFF
            z = data[register] == 0
            c = False
            pc += 2
            continue

        if opcode & 0xFFF8 == 0x5240:
            register = opcode & 7
            data[register] = (data[register] + 1) & 0xFFFF
            z = data[register] == 0
            c = False
            pc += 1
            continue

        if opcode & 0xFFF8 == 0x5340:
            register = opcode & 7
            before = data[register] & 0xFFFF
            data[register] = (before - 1) & 0xFFFF
            z = data[register] == 0
            c = before == 0
            pc += 1
            continue

        if opcode == 0x31FC:
            immediate = words[pc + 1]
            absolute = words[pc + 2]
            memory[absolute] = immediate
            writes.append((absolute, immediate))
            z = immediate == 0
            c = False
            pc += 3
            continue

        if opcode & 0xFFF8 == 0x31C0:
            register = opcode & 7
            absolute = words[pc + 1]
            value = data[register] & 0xFFFF
            memory[absolute] = value
            writes.append((absolute, value))
            z = value == 0
            c = False
            pc += 2
            continue

        condition = (opcode >> 8) & 0xF
        if opcode & 0xF000 == 0x6000 and (opcode & 0xFF) == 0:
            displacement = words[pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            take = (
                condition == 0
                or (condition == 2 and not c and not z)
                or (condition == 6 and not z)
                or (condition == 7 and z)
            )
            if take:
                target_byte = (pc * 2 + 2) + displacement
                if target_byte & 1:
                    raise AssertionError("generated Bcc.W target is odd")
                pc = target_byte // 2
            else:
                pc += 2
            continue

        raise AssertionError(f"unexpected generated 68K opcode 0x{opcode:04X} at word {pc}")

    raise AssertionError("generated resident decoder did not reach a terminal hold")


def _assert_acknowledged(test: unittest.TestCase, program: SaturnMidiProgram) -> None:
    image = build_srk_saturn_midi_68k_resident_decoder_image()
    memory, _, _, _ = _run_reviewed_subset(image.words, _sound_ram_words(program))
    count = len(program.records)
    final_time = program.records[-1].time_us

    test.assertEqual(memory[_MB_READ_INDEX], count)
    test.assertEqual(memory[_MB_READ_SEQUENCE], memory[_MB_WRITE_SEQUENCE])
    test.assertEqual(memory[_MB_LAST_ERROR], 0)
    test.assertEqual(
        memory[
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_PROCESSED_OFFSET
        ],
        count,
    )
    test.assertEqual(
        memory[
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET
        ],
        count,
    )
    test.assertEqual(
        memory[
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET
        ],
        (final_time >> 16) & 0xFFFF,
    )
    test.assertEqual(
        memory[
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET
        ],
        final_time & 0xFFFF,
    )
    test.assertEqual(
        memory[
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_READY_OFFSET
        ],
        1,
    )


class SaturnMidi68KResidentDecoderTests(unittest.TestCase):
    def test_image_is_deterministic_content_independent_and_bounded(self):
        first = build_srk_saturn_midi_68k_resident_decoder_image()
        second = build_srk_saturn_midi_68k_resident_decoder_image()

        self.assertEqual(SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS, 0x00004000)
        self.assertEqual(SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS, 32)
        self.assertEqual(first.words, second.words)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.byte_size, first.word_count * 2)
        self.assertLess(first.end_address, SATURN_MIDI_68K_RESIDENT_DECODER_MAX_END)

    def test_machine_image_consumes_the_existing_canonical_batch_dynamically(self):
        program = build_srk_saturn_midi_bridge_assets().program
        self.assertEqual(len(program.records), 27)
        _assert_acknowledged(self, program)

    def test_runtime_count_is_general_from_one_through_full_queue_capacity(self):
        one = _one_record_program()
        maximum = _max_record_program()

        self.assertEqual(len(one.records), 1)
        self.assertEqual(len(maximum.records), 32)
        _assert_acknowledged(self, one)
        _assert_acknowledged(self, maximum)

    def test_invalid_channel_opcode_and_data_are_rejected_without_ack(self):
        image = build_srk_saturn_midi_68k_resident_decoder_image()

        bad_channel = _sound_ram_words(_one_record_program())
        bad_channel[SATURN_MIDI_QUEUE_ADDRESS + 4] = (
            (int(SaturnMidiOpcode.NOTE_ON) << 8) | 16
        )
        bad_channel, _, _, _ = _run_reviewed_subset(image.words, bad_channel)
        self.assertEqual(bad_channel[_MB_READ_INDEX], 0)
        self.assertEqual(bad_channel[_MB_READ_SEQUENCE], 0)
        self.assertEqual(bad_channel[_MB_LAST_ERROR], SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_RECORD)

        bad_opcode = _sound_ram_words(_one_record_program())
        bad_opcode[SATURN_MIDI_QUEUE_ADDRESS + 4] = (8 << 8) | 0
        bad_opcode, _, _, _ = _run_reviewed_subset(image.words, bad_opcode)
        self.assertEqual(bad_opcode[_MB_READ_INDEX], 0)
        self.assertEqual(bad_opcode[_MB_LAST_ERROR], SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_RECORD)

        bad_data = _sound_ram_words(_one_record_program())
        bad_data[SATURN_MIDI_QUEUE_ADDRESS + 6] = 0x8001
        bad_data, _, _, _ = _run_reviewed_subset(image.words, bad_data)
        self.assertEqual(bad_data[_MB_READ_INDEX], 0)
        self.assertEqual(bad_data[_MB_LAST_ERROR], SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_RECORD)
        self.assertEqual(
            bad_data[
                SATURN_MIDI_68K_TELEMETRY_ADDRESS
                + SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET
            ],
            0,
        )

    def test_mailbox_count_index_and_sequence_contract_is_bounded(self):
        image = build_srk_saturn_midi_68k_resident_decoder_image()

        empty = _sound_ram_words(_one_record_program())
        empty[_MB_QUEUE_COUNT] = 0
        empty[_MB_WRITE_INDEX] = 0
        empty, _, _, _ = _run_reviewed_subset(image.words, empty)
        self.assertEqual(empty[_MB_LAST_ERROR], SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_EMPTY)

        too_many = _sound_ram_words(_one_record_program())
        too_many[_MB_QUEUE_COUNT] = 33
        too_many[_MB_WRITE_INDEX] = 33
        too_many, _, _, _ = _run_reviewed_subset(image.words, too_many)
        self.assertEqual(too_many[_MB_LAST_ERROR], SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_COUNT)

        mismatch = _sound_ram_words(_one_record_program())
        mismatch[_MB_WRITE_INDEX] = 2
        mismatch, _, _, _ = _run_reviewed_subset(image.words, mismatch)
        self.assertEqual(mismatch[_MB_LAST_ERROR], SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_COUNT)

        zero_sequence = _sound_ram_words(_one_record_program())
        zero_sequence[_MB_WRITE_SEQUENCE] = 0
        zero_sequence, _, _, _ = _run_reviewed_subset(image.words, zero_sequence)
        self.assertEqual(
            zero_sequence[_MB_LAST_ERROR],
            SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_CONTRACT,
        )

    def test_queue_reads_are_pointer_driven_and_cover_exact_runtime_count(self):
        program = _max_record_program()
        image = build_srk_saturn_midi_68k_resident_decoder_image()
        _, _, reads, _ = _run_reviewed_subset(image.words, _sound_ram_words(program))

        queue_reads = tuple(
            read
            for read in reads
            if SATURN_MIDI_QUEUE_ADDRESS
            <= read
            < SATURN_MIDI_QUEUE_ADDRESS + SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS * 8
        )
        self.assertEqual(
            queue_reads,
            tuple(
                range(
                    SATURN_MIDI_QUEUE_ADDRESS,
                    SATURN_MIDI_QUEUE_ADDRESS + SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS * 8,
                    2,
                )
            ),
        )

    def test_runtime_writes_remain_silent_and_do_not_mutate_command_state(self):
        image = build_srk_saturn_midi_68k_resident_decoder_image()
        _, writes, _, _ = _run_reviewed_subset(
            image.words,
            _sound_ram_words(_max_record_program()),
        )

        self.assertTrue(writes)
        self.assertTrue(all(0 <= absolute < 0x2000 for absolute, _ in writes))
        self.assertFalse(any(0x1200 <= absolute < 0x1D00 for absolute, _ in writes))

    def test_generated_c_representation_is_deterministic_inert_and_silent(self):
        image = build_srk_saturn_midi_68k_resident_decoder_image()
        header = render_srk_saturn_midi_68k_resident_decoder_header()
        source = render_srk_saturn_midi_68k_resident_decoder_source()

        self.assertIn(
            f"PROGRAM_WORD_COUNT {image.word_count}u",
            header,
        )
        self.assertIn(
            f"PROGRAM_BYTE_SIZE {image.byte_size}u",
            header,
        )
        self.assertIn("MAX_RECORDS 32u", header)
        self.assertIn("0x41F8u", source)
        self.assertIn("0x3418u", source)
        self.assertIn("0x5340u", source)
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
            / "midi_68k_resident_decoder.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("0x25B00000", module_text)
        self.assertNotIn("0x2010001F", module_text)


if __name__ == "__main__":
    unittest.main()
