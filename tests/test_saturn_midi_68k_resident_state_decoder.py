"""Regression tests for Phase-B dynamic resident MIDI state mutation."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_ACTIVE_NOTES_BYTES,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_CONTROLLER_BYTES,
    SATURN_MIDI_68K_STATE_ADDRESS,
    SATURN_MIDI_68K_CHANNEL_STATE_TOTAL_BYTES,
    SATURN_MIDI_68K_TELEMETRY_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
    simulate_srk_saturn_midi_68k_command_engine,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder import (
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_RECORD,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_END,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET,
    build_srk_saturn_midi_68k_resident_state_decoder_image,
    render_srk_saturn_midi_68k_resident_state_decoder_header,
    render_srk_saturn_midi_68k_resident_state_decoder_source,
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
_MB_READ_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 10
_MB_READ_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 14
_MB_LAST_ERROR = SATURN_MIDI_MAILBOX_ADDRESS + 20
_RAM_SIZE = 0x8000


def _write_word(memory: bytearray, address: int, value: int) -> None:
    memory[address] = (value >> 8) & 0xFF
    memory[address + 1] = value & 0xFF


def _read_word(memory: bytearray, address: int) -> int:
    return (memory[address] << 8) | memory[address + 1]


def _sound_ram(program: SaturnMidiProgram) -> bytearray:
    memory = bytearray(_RAM_SIZE)
    for index, word in enumerate(build_saturn_midi_mailbox_words(program)):
        _write_word(memory, SATURN_MIDI_MAILBOX_ADDRESS + index * 2, word)
    for index, word in enumerate(pack_saturn_midi_queue_words(program)):
        _write_word(memory, SATURN_MIDI_QUEUE_ADDRESS + index * 2, word)
    return memory


def _run_reviewed_subset(
    words: tuple[int, ...],
    memory: bytearray,
    *,
    max_steps: int = 500000,
):
    """Execute exactly the MC68000 subset emitted by the Phase-B generator."""

    data = [0] * 8
    address = [0] * 8
    pc = 0
    z = False
    c = False
    writes: list[tuple[int, int]] = []
    reads: list[tuple[int, int]] = []

    def compare(destination: int, source: int) -> None:
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
            reads.append((absolute, 2))
            data[register] = _read_word(memory, absolute)
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

        if opcode & 0xF1FF == 0x3018:
            register = (opcode >> 9) & 7
            absolute = address[0]
            reads.append((absolute, 2))
            data[register] = _read_word(memory, absolute)
            address[0] += 2
            z = data[register] == 0
            c = False
            pc += 1
            continue

        if opcode & 0xF1FF == 0x1018:
            register = (opcode >> 9) & 7
            absolute = address[0]
            reads.append((absolute, 1))
            data[register] = (data[register] & 0xFFFFFF00) | memory[absolute]
            address[0] += 1
            z = (data[register] & 0xFF) == 0
            c = False
            pc += 1
            continue

        if opcode & 0xF1FF == 0x41F8:
            register = (opcode >> 9) & 7
            address[register] = words[pc + 1]
            pc += 2
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
            compare(data[register], words[pc + 1])
            pc += 2
            continue

        if opcode & 0xF1F8 == 0xB040:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            compare(data[destination], data[source])
            pc += 1
            continue

        if opcode & 0xFFF8 == 0x0240:
            register = opcode & 7
            data[register] &= words[pc + 1]
            data[register] &= 0xFFFF
            z = data[register] == 0
            c = False
            pc += 2
            continue

        if (opcode & 0xF0C0) == 0x5040 and ((opcode >> 3) & 7) == 0:
            register = opcode & 7
            encoded = (opcode >> 9) & 7
            immediate = encoded if encoded else 8
            before = data[register] & 0xFFFF
            if opcode & 0x0100:
                data[register] = (before - immediate) & 0xFFFF
                c = before < immediate
            else:
                total = before + immediate
                data[register] = total & 0xFFFF
                c = total > 0xFFFF
            z = data[register] == 0
            pc += 1
            continue

        if opcode & 0xF1F8 == 0xD040:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            total = (data[destination] & 0xFFFF) + (data[source] & 0xFFFF)
            data[destination] = total & 0xFFFF
            z = data[destination] == 0
            c = total > 0xFFFF
            pc += 1
            continue

        if opcode == 0x31FC:
            value = words[pc + 1]
            absolute = words[pc + 2]
            _write_word(memory, absolute, value)
            writes.append((absolute, 2))
            z = value == 0
            c = False
            pc += 3
            continue

        if opcode & 0xFFF8 == 0x31C0:
            register = opcode & 7
            absolute = words[pc + 1]
            _write_word(memory, absolute, data[register])
            writes.append((absolute, 2))
            z = (data[register] & 0xFFFF) == 0
            c = False
            pc += 2
            continue

        if opcode & 0xF1F8 == 0x3028:
            destination = (opcode >> 9) & 7
            source_address = opcode & 7
            displacement = words[pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            absolute = address[source_address] + displacement
            reads.append((absolute, 2))
            data[destination] = _read_word(memory, absolute)
            z = data[destination] == 0
            c = False
            pc += 2
            continue

        if opcode & 0xF1F8 == 0x3140:
            destination_address = (opcode >> 9) & 7
            source = opcode & 7
            displacement = words[pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            absolute = address[destination_address] + displacement
            _write_word(memory, absolute, data[source])
            writes.append((absolute, 2))
            z = (data[source] & 0xFFFF) == 0
            c = False
            pc += 2
            continue

        if opcode & 0xF1F8 == 0xD0C0:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            value = data[source] & 0xFFFF
            if value & 0x8000:
                value -= 0x10000
            address[destination] = (address[destination] + value) & 0xFFFFFFFF
            pc += 1
            continue

        if opcode & 0xF1F8 == 0x1080:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            memory[address[destination]] = data[source] & 0xFF
            writes.append((address[destination], 1))
            z = (data[source] & 0xFF) == 0
            c = False
            pc += 1
            continue

        if opcode & 0xF1F8 == 0x01D0:
            destination = opcode & 7
            bit_register = (opcode >> 9) & 7
            bit = data[bit_register] & 7
            mask = 1 << bit
            old_set = (memory[address[destination]] & mask) != 0
            z = not old_set
            memory[address[destination]] |= mask
            writes.append((address[destination], 1))
            pc += 1
            continue

        if opcode & 0xF1F8 == 0x0190:
            destination = opcode & 7
            bit_register = (opcode >> 9) & 7
            bit = data[bit_register] & 7
            mask = 1 << bit
            old_set = (memory[address[destination]] & mask) != 0
            z = not old_set
            memory[address[destination]] &= (~mask) & 0xFF
            writes.append((address[destination], 1))
            pc += 1
            continue

        condition = (opcode >> 8) & 0xF
        if opcode & 0xF000 == 0x6000 and (opcode & 0xFF) == 0:
            displacement = words[pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            take = (
                condition == 0
                or (condition == 2 and not c and not z)
                or (condition == 5 and c)
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

    raise AssertionError("generated resident state decoder did not reach terminal hold")


def _state_words(memory: bytearray) -> tuple[int, ...]:
    return tuple(
        _read_word(memory, SATURN_MIDI_68K_STATE_ADDRESS + offset)
        for offset in range(0, SATURN_MIDI_68K_CHANNEL_STATE_TOTAL_BYTES, 2)
    )


def _assert_machine_matches_model(test: unittest.TestCase, program: SaturnMidiProgram) -> None:
    image = build_srk_saturn_midi_68k_resident_state_decoder_image()
    memory, writes, _reads, _pc = _run_reviewed_subset(image.words, _sound_ram(program))
    model = simulate_srk_saturn_midi_68k_command_engine(program)

    test.assertEqual(_read_word(memory, _MB_READ_INDEX), len(program.records))
    test.assertEqual(_read_word(memory, _MB_READ_SEQUENCE), 1)
    test.assertEqual(_read_word(memory, _MB_LAST_ERROR), 0)
    test.assertEqual(
        _read_word(
            memory,
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET,
        ),
        len(program.records),
    )
    test.assertEqual(
        _read_word(
            memory,
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET,
        ),
        1,
    )
    test.assertEqual(_state_words(memory), pack_srk_saturn_midi_68k_state_words(model))
    test.assertEqual(
        bytes(memory[
            SATURN_MIDI_68K_CONTROLLER_ADDRESS:
            SATURN_MIDI_68K_CONTROLLER_ADDRESS + SATURN_MIDI_68K_CONTROLLER_BYTES
        ]),
        pack_srk_saturn_midi_68k_controller_bytes(model),
    )
    test.assertEqual(
        bytes(memory[
            SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:
            SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES
        ]),
        pack_srk_saturn_midi_68k_active_note_bitmap(model),
    )
    test.assertTrue(writes)
    test.assertTrue(all(address < 0x2000 for address, _size in writes))


class SaturnMidi68KResidentStateDecoderTests(unittest.TestCase):
    def test_image_geometry_and_hash_are_pinned(self):
        image = build_srk_saturn_midi_68k_resident_state_decoder_image()
        self.assertEqual(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS, 0x4000)
        self.assertEqual(image.word_count, 4898)
        self.assertEqual(image.byte_size, 9796)
        self.assertEqual(image.end_address, 0x6644)
        self.assertLess(image.end_address, SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_END)
        self.assertEqual(
            image.sha256,
            "39d5c1116affa95e2be7d5f94342e0ba70bfebf845b6f2cce292946894bd5bb9",
        )

    def test_canonical_27_record_program_matches_complete_host_state_model(self):
        program = build_srk_saturn_midi_bridge_assets().program
        self.assertEqual(len(program.records), 27)
        _assert_machine_matches_model(self, program)

    def test_all_seven_opcodes_across_channels_match_model(self):
        program = SaturnMidiProgram(
            records=(
                SaturnMidiRecord(1000, SaturnMidiOpcode.NOTE_ON, 0, 60, 100),
                SaturnMidiRecord(2000, SaturnMidiOpcode.POLY_AFTERTOUCH, 1, 61, 55),
                SaturnMidiRecord(3000, SaturnMidiOpcode.CONTROL_CHANGE, 2, 7, 91),
                SaturnMidiRecord(4000, SaturnMidiOpcode.PROGRAM_CHANGE, 3, 12, 0),
                SaturnMidiRecord(5000, SaturnMidiOpcode.CHANNEL_PRESSURE, 4, 71, 0),
                SaturnMidiRecord(6000, SaturnMidiOpcode.PITCH_BEND, 5, 1, 64),
                SaturnMidiRecord(7000, SaturnMidiOpcode.NOTE_OFF, 0, 60, 12),
            ),
            duration_us=7000,
        )
        _assert_machine_matches_model(self, program)

    def test_controller_bank_volume_pan_expression_and_sustain_matrix_match_model(self):
        records = tuple(
            SaturnMidiRecord(index + 1, SaturnMidiOpcode.CONTROL_CHANGE, 9, controller, value)
            for index, (controller, value) in enumerate(
                ((0, 2), (32, 4), (7, 90), (10, 99), (11, 88), (64, 127), (64, 0), (73, 45))
            )
        )
        _assert_machine_matches_model(
            self,
            SaturnMidiProgram(records=records, duration_us=records[-1].time_us),
        )

    def test_duplicate_notes_and_zero_velocity_note_on_match_bitmap_model(self):
        records = (
            SaturnMidiRecord(1, SaturnMidiOpcode.NOTE_ON, 3, 64, 10),
            SaturnMidiRecord(2, SaturnMidiOpcode.NOTE_ON, 3, 64, 20),
            SaturnMidiRecord(3, SaturnMidiOpcode.NOTE_OFF, 3, 64, 0),
            SaturnMidiRecord(4, SaturnMidiOpcode.NOTE_OFF, 3, 64, 0),
            SaturnMidiRecord(5, SaturnMidiOpcode.NOTE_ON, 3, 65, 12),
            SaturnMidiRecord(6, SaturnMidiOpcode.NOTE_ON, 3, 65, 0),
        )
        _assert_machine_matches_model(
            self,
            SaturnMidiProgram(records=records, duration_us=6),
        )

    def test_full_32_record_runtime_batch_matches_model(self):
        records = tuple(
            SaturnMidiRecord(
                index * 1000,
                SaturnMidiOpcode((index % 7) + 1),
                index % 16,
                (index * 3) & 0x7F,
                (index * 5) & 0x7F,
            )
            for index in range(32)
        )
        _assert_machine_matches_model(
            self,
            SaturnMidiProgram(records=records, duration_us=records[-1].time_us),
        )

    def test_invalid_record_fails_before_state_mutation(self):
        program = SaturnMidiProgram(
            records=(SaturnMidiRecord(1000, SaturnMidiOpcode.NOTE_ON, 0, 60, 100),),
            duration_us=1000,
        )
        memory = _sound_ram(program)
        state_start = SATURN_MIDI_68K_STATE_ADDRESS
        state_end = SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES
        sentinel = bytes((index * 37 + 11) & 0xFF for index in range(state_end - state_start))
        memory[state_start:state_end] = sentinel
        memory[SATURN_MIDI_QUEUE_ADDRESS + 4] = 8

        image = build_srk_saturn_midi_68k_resident_state_decoder_image()
        memory, _writes, _reads, _pc = _run_reviewed_subset(image.words, memory)

        self.assertEqual(memory[state_start:state_end], sentinel)
        self.assertEqual(_read_word(memory, _MB_READ_INDEX), 0)
        self.assertEqual(_read_word(memory, _MB_READ_SEQUENCE), 0)
        self.assertEqual(
            _read_word(memory, _MB_LAST_ERROR),
            SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_RECORD,
        )

    def test_generated_c_is_inert_constant_data_and_contains_no_scsp_access(self):
        header = render_srk_saturn_midi_68k_resident_state_decoder_header()
        source = render_srk_saturn_midi_68k_resident_state_decoder_source()
        self.assertIn("PROGRAM_WORD_COUNT 4898u", header)
        self.assertIn("PROGRAM_BYTE_SIZE 9796u", header)
        self.assertIn(
            "const unsigned short srk_saturn_midi_68k_resident_state_decoder_program[]",
            source,
        )
        combined = (header + source).lower()
        for forbidden in ("0x25b", "scsp", "smpc", "sndon", "sndoff"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
