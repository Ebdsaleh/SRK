"""Instruction-level regression for the continuous MC68EC000 stream service."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_ACTIVE_NOTES_BYTES,
    SATURN_MIDI_68K_CHANNEL_STATE_TOTAL_BYTES,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_CONTROLLER_BYTES,
    SATURN_MIDI_68K_STATE_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_service import (
    SATURN_MIDI_68K_RESIDENT_STREAM_MAX_END,
    SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_stream_service_image,
    render_srk_saturn_midi_68k_resident_stream_service_header,
    render_srk_saturn_midi_68k_resident_stream_service_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
    SATURN_MIDI_68K_STREAM_ERROR_SEQUENCE,
    SATURN_MIDI_68K_STREAM_ERROR_TIMESTAMP,
    SATURN_MIDI_68K_STREAM_FLAG_ERROR,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    build_srk_saturn_midi_stream_batches,
    simulate_srk_saturn_midi_stream_timeline,
)
from rikai_kotoba.hardware.saturn.midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_MAILBOX_MAGIC0,
    SATURN_MIDI_MAILBOX_MAGIC1,
    SATURN_MIDI_MAILBOX_VERSION,
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_CAPACITY,
)
from rikai_kotoba.hardware.saturn.midi_mailbox import (
    SATURN_MIDI_MAILBOX_FLAG_READY,
    pack_saturn_midi_queue_words,
)
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
)


_RAM_SIZE = 0x8000
_MB_FLAGS = SATURN_MIDI_MAILBOX_ADDRESS + 6
_MB_WRITE_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 8
_MB_READ_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 10
_MB_WRITE_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 12
_MB_READ_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 14
_MB_QUEUE_CAPACITY = SATURN_MIDI_MAILBOX_ADDRESS + 16
_MB_QUEUE_COUNT = SATURN_MIDI_MAILBOX_ADDRESS + 18
_MB_LAST_ERROR = SATURN_MIDI_MAILBOX_ADDRESS + 20


def _write_word(memory: bytearray, address: int, value: int) -> None:
    memory[address] = (value >> 8) & 0xFF
    memory[address + 1] = value & 0xFF


def _read_word(memory: bytearray, address: int) -> int:
    return (memory[address] << 8) | memory[address + 1]


def _svc(offset: int) -> int:
    return SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS + offset


def _program(count: int = 40) -> SaturnMidiProgram:
    opcodes = tuple(SaturnMidiOpcode)
    records = []
    for index in range(count):
        opcode = opcodes[index % len(opcodes)]
        data0 = (40 + index) & 0x7F
        data1 = (80 + index) & 0x7F
        if opcode in (SaturnMidiOpcode.PROGRAM_CHANGE, SaturnMidiOpcode.CHANNEL_PRESSURE):
            data1 = 0
        records.append(
            SaturnMidiRecord(
                time_us=(index + 1) * 1000,
                opcode=opcode,
                channel=index % 4,
                data0=data0,
                data1=data1,
            )
        )
    return SaturnMidiProgram(records=tuple(records), duration_us=records[-1].time_us)


def _publish_clock(memory: bytearray, now_us: int) -> None:
    generation_address = _svc(SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET)
    generation = (_read_word(memory, generation_address) + 1) & 0xFFFF
    if (generation & 1) == 0:
        generation = (generation + 1) & 0xFFFF
    _write_word(memory, generation_address, generation)
    _write_word(memory, _svc(SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET), (now_us >> 16) & 0xFFFF)
    _write_word(memory, _svc(SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET), now_us & 0xFFFF)
    _write_word(memory, generation_address, (generation + 1) & 0xFFFF)


def _publish_batch(memory: bytearray, sequence: int, records: tuple[SaturnMidiRecord, ...]) -> None:
    program = SaturnMidiProgram(records=records, duration_us=records[-1].time_us)
    _write_word(memory, _MB_FLAGS, 0)
    for index, word in enumerate(pack_saturn_midi_queue_words(program)):
        _write_word(memory, SATURN_MIDI_QUEUE_ADDRESS + index * 2, word)
    _write_word(memory, SATURN_MIDI_MAILBOX_ADDRESS + 0, SATURN_MIDI_MAILBOX_MAGIC0)
    _write_word(memory, SATURN_MIDI_MAILBOX_ADDRESS + 2, SATURN_MIDI_MAILBOX_MAGIC1)
    _write_word(memory, SATURN_MIDI_MAILBOX_ADDRESS + 4, SATURN_MIDI_MAILBOX_VERSION)
    _write_word(memory, _MB_WRITE_SEQUENCE, sequence)
    _write_word(memory, _MB_WRITE_INDEX, len(records))
    _write_word(memory, _MB_QUEUE_CAPACITY, SATURN_MIDI_QUEUE_CAPACITY)
    _write_word(memory, _MB_QUEUE_COUNT, len(records))
    _write_word(memory, _MB_LAST_ERROR, 0)
    _write_word(memory, _MB_FLAGS, SATURN_MIDI_MAILBOX_FLAG_READY)


class _Machine:
    def __init__(self, words: tuple[int, ...], memory: bytearray) -> None:
        self.words = words
        self.memory = memory
        self.data = [0] * 8
        self.address = [0] * 8
        self.pc = 0
        self.z = False
        self.c = False
        self.steps = 0
        self.writes: list[tuple[int, int]] = []

    def _compare(self, destination: int, source: int) -> None:
        destination &= 0xFFFF
        source &= 0xFFFF
        self.z = destination == source
        self.c = destination < source

    def step(self) -> None:
        words = self.words
        opcode = words[self.pc]
        self.steps += 1

        if opcode == 0x60FE:
            return

        if opcode & 0xF1FF == 0x3038:
            register = (opcode >> 9) & 7
            absolute = words[self.pc + 1]
            self.data[register] = _read_word(self.memory, absolute)
            self.z = self.data[register] == 0
            self.c = False
            self.pc += 2
            return

        if opcode & 0xF1FF == 0x303C:
            register = (opcode >> 9) & 7
            self.data[register] = words[self.pc + 1] & 0xFFFF
            self.z = self.data[register] == 0
            self.c = False
            self.pc += 2
            return

        if opcode & 0xF1FF == 0x3018:
            register = (opcode >> 9) & 7
            absolute = self.address[0]
            self.data[register] = _read_word(self.memory, absolute)
            self.address[0] += 2
            self.z = self.data[register] == 0
            self.c = False
            self.pc += 1
            return

        if opcode & 0xF1FF == 0x1018:
            register = (opcode >> 9) & 7
            absolute = self.address[0]
            self.data[register] = (self.data[register] & 0xFFFFFF00) | self.memory[absolute]
            self.address[0] += 1
            self.z = (self.data[register] & 0xFF) == 0
            self.c = False
            self.pc += 1
            return

        if opcode & 0xF1FF == 0x41F8:
            register = (opcode >> 9) & 7
            self.address[register] = words[self.pc + 1]
            self.pc += 2
            return

        if opcode & 0xF1F8 == 0x3000:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            self.data[destination] = self.data[source] & 0xFFFF
            self.z = self.data[destination] == 0
            self.c = False
            self.pc += 1
            return

        if opcode & 0xFFF8 == 0x0C40:
            register = opcode & 7
            self._compare(self.data[register], words[self.pc + 1])
            self.pc += 2
            return

        if opcode & 0xF1F8 == 0xB040:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            self._compare(self.data[destination], self.data[source])
            self.pc += 1
            return

        if opcode & 0xFFF8 == 0x0240:
            register = opcode & 7
            self.data[register] &= words[self.pc + 1]
            self.data[register] &= 0xFFFF
            self.z = self.data[register] == 0
            self.c = False
            self.pc += 2
            return

        if (opcode & 0xF0C0) == 0x5040 and ((opcode >> 3) & 7) == 0:
            register = opcode & 7
            encoded = (opcode >> 9) & 7
            immediate = encoded if encoded else 8
            before = self.data[register] & 0xFFFF
            if opcode & 0x0100:
                self.data[register] = (before - immediate) & 0xFFFF
                self.c = before < immediate
            else:
                total = before + immediate
                self.data[register] = total & 0xFFFF
                self.c = total > 0xFFFF
            self.z = self.data[register] == 0
            self.pc += 1
            return

        if opcode & 0xF1F8 == 0xD040:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            total = (self.data[destination] & 0xFFFF) + (self.data[source] & 0xFFFF)
            self.data[destination] = total & 0xFFFF
            self.z = self.data[destination] == 0
            self.c = total > 0xFFFF
            self.pc += 1
            return

        if opcode == 0x31FC:
            value = words[self.pc + 1]
            absolute = words[self.pc + 2]
            _write_word(self.memory, absolute, value)
            self.writes.append((absolute, 2))
            self.z = value == 0
            self.c = False
            self.pc += 3
            return

        if opcode & 0xFFF8 == 0x31C0:
            register = opcode & 7
            absolute = words[self.pc + 1]
            _write_word(self.memory, absolute, self.data[register])
            self.writes.append((absolute, 2))
            self.z = (self.data[register] & 0xFFFF) == 0
            self.c = False
            self.pc += 2
            return

        if opcode & 0xF1F8 == 0x3028:
            destination = (opcode >> 9) & 7
            source_address = opcode & 7
            displacement = words[self.pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            absolute = self.address[source_address] + displacement
            self.data[destination] = _read_word(self.memory, absolute)
            self.z = self.data[destination] == 0
            self.c = False
            self.pc += 2
            return

        if opcode & 0xF1F8 == 0x3140:
            destination_address = (opcode >> 9) & 7
            source = opcode & 7
            displacement = words[self.pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            absolute = self.address[destination_address] + displacement
            _write_word(self.memory, absolute, self.data[source])
            self.writes.append((absolute, 2))
            self.z = (self.data[source] & 0xFFFF) == 0
            self.c = False
            self.pc += 2
            return

        if opcode & 0xF1F8 == 0xD0C0:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            value = self.data[source] & 0xFFFF
            if value & 0x8000:
                value -= 0x10000
            self.address[destination] = (self.address[destination] + value) & 0xFFFFFFFF
            self.pc += 1
            return

        if opcode & 0xF1F8 == 0x1080:
            destination = (opcode >> 9) & 7
            source = opcode & 7
            self.memory[self.address[destination]] = self.data[source] & 0xFF
            self.writes.append((self.address[destination], 1))
            self.z = (self.data[source] & 0xFF) == 0
            self.c = False
            self.pc += 1
            return

        if opcode & 0xF1F8 == 0x01D0:
            destination = opcode & 7
            bit_register = (opcode >> 9) & 7
            bit = self.data[bit_register] & 7
            mask = 1 << bit
            old_set = (self.memory[self.address[destination]] & mask) != 0
            self.z = not old_set
            self.memory[self.address[destination]] |= mask
            self.writes.append((self.address[destination], 1))
            self.pc += 1
            return

        if opcode & 0xF1F8 == 0x0190:
            destination = opcode & 7
            bit_register = (opcode >> 9) & 7
            bit = self.data[bit_register] & 7
            mask = 1 << bit
            old_set = (self.memory[self.address[destination]] & mask) != 0
            self.z = not old_set
            self.memory[self.address[destination]] &= (~mask) & 0xFF
            self.writes.append((self.address[destination], 1))
            self.pc += 1
            return

        condition = (opcode >> 8) & 0xF
        if opcode & 0xF000 == 0x6000 and (opcode & 0xFF) == 0:
            displacement = words[self.pc + 1]
            if displacement & 0x8000:
                displacement -= 0x10000
            take = (
                condition == 0
                or (condition == 2 and not self.c and not self.z)
                or (condition == 5 and self.c)
                or (condition == 6 and not self.z)
                or (condition == 7 and self.z)
            )
            if take:
                target_byte = (self.pc * 2 + 2) + displacement
                if target_byte & 1:
                    raise AssertionError("generated Bcc.W target is odd")
                self.pc = target_byte // 2
            else:
                self.pc += 2
            return

        raise AssertionError(f"unexpected generated 68K opcode 0x{opcode:04X} at word {self.pc}")

    def run_until(self, predicate, *, max_steps: int = 800000) -> None:
        for _ in range(max_steps):
            if predicate():
                return
            before = self.pc
            self.step()
            if self.words[before] == 0x60FE and not predicate():
                raise AssertionError("resident service entered terminal error hold")
        raise AssertionError("resident stream service did not reach expected boundary")


def _state_words(memory: bytearray) -> tuple[int, ...]:
    return tuple(
        _read_word(memory, SATURN_MIDI_68K_STATE_ADDRESS + offset)
        for offset in range(0, SATURN_MIDI_68K_CHANNEL_STATE_TOTAL_BYTES, 2)
    )


class SaturnMidi68KResidentStreamServiceTests(unittest.TestCase):
    def test_image_fits_reviewed_program_envelope_and_generated_c_is_inert(self):
        image = build_srk_saturn_midi_68k_resident_stream_service_image()
        self.assertEqual(SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS, 0x4000)
        self.assertGreater(image.word_count, 4898)
        self.assertLess(image.end_address, SATURN_MIDI_68K_RESIDENT_STREAM_MAX_END)
        self.assertEqual(image.sha256, build_srk_saturn_midi_68k_resident_stream_service_image().sha256)
        generated = (
            render_srk_saturn_midi_68k_resident_stream_service_header()
            + render_srk_saturn_midi_68k_resident_stream_service_source()
        ).upper()
        self.assertNotIn("SCSP", generated)
        self.assertNotIn("SMPC", generated)
        self.assertNotIn("0X25B", generated)

    def test_exact_machine_words_wait_refill_ack_and_preserve_complete_state(self):
        program = _program(40)
        batches = build_srk_saturn_midi_stream_batches(program)
        self.assertEqual(tuple(len(batch.records) for batch in batches), (32, 8))

        memory = bytearray(_RAM_SIZE)
        image = build_srk_saturn_midi_68k_resident_stream_service_image()
        machine = _Machine(image.words, memory)
        _publish_clock(memory, 0)
        _publish_batch(memory, batches[0].sequence, batches[0].records)

        machine.run_until(
            lambda: _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
            == SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME
            and _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET)) == 0
        )
        self.assertEqual(_read_word(memory, _MB_READ_SEQUENCE), 0)
        self.assertEqual(_read_word(memory, _MB_READ_INDEX), 0)

        _publish_clock(memory, 15000)
        machine.run_until(
            lambda: _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
            == SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME
            and _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET)) == 15
        )
        self.assertEqual(_read_word(memory, _MB_READ_SEQUENCE), 0)

        _publish_clock(memory, 32000)
        machine.run_until(lambda: _read_word(memory, _MB_READ_SEQUENCE) == 1)
        self.assertEqual(_read_word(memory, _MB_READ_INDEX), 32)

        _publish_batch(memory, batches[1].sequence, batches[1].records)
        machine.run_until(
            lambda: _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
            == SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME
            and _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET)) == 0
        )
        self.assertEqual(_read_word(memory, _MB_READ_SEQUENCE), 1)

        _publish_clock(memory, 40000)
        machine.run_until(lambda: _read_word(memory, _MB_READ_SEQUENCE) == 2)
        self.assertEqual(_read_word(memory, _MB_READ_INDEX), 8)
        self.assertEqual(_read_word(memory, _MB_LAST_ERROR), 0)

        model = simulate_srk_saturn_midi_stream_timeline(program, (40000,))[-1]
        self.assertEqual(_state_words(memory), pack_srk_saturn_midi_68k_state_words(model))
        self.assertEqual(
            bytes(memory[
                SATURN_MIDI_68K_CONTROLLER_ADDRESS:
                SATURN_MIDI_68K_CONTROLLER_ADDRESS + SATURN_MIDI_68K_CONTROLLER_BYTES
            ]),
            pack_srk_saturn_midi_68k_controller_bytes(model),
        )
        self.assertEqual(
            bytes(memory[
                SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:
                SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES
            ]),
            pack_srk_saturn_midi_68k_active_note_bitmap(model),
        )
        self.assertTrue(machine.writes)
        self.assertTrue(all(address < 0x2000 for address, _size in machine.writes))

    def test_wrong_refill_sequence_fails_before_second_batch_mutation(self):
        program = _program(33)
        batches = build_srk_saturn_midi_stream_batches(program)
        memory = bytearray(_RAM_SIZE)
        image = build_srk_saturn_midi_68k_resident_stream_service_image()
        machine = _Machine(image.words, memory)
        _publish_clock(memory, 32000)
        _publish_batch(memory, 1, batches[0].records)
        machine.run_until(lambda: _read_word(memory, _MB_READ_SEQUENCE) == 1)
        before = bytes(memory[SATURN_MIDI_68K_STATE_ADDRESS:SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES])

        _publish_batch(memory, 3, batches[1].records)
        machine.run_until(
            lambda: _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
            == SATURN_MIDI_68K_STREAM_FLAG_ERROR
        )
        self.assertEqual(
            _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET)),
            SATURN_MIDI_68K_STREAM_ERROR_SEQUENCE,
        )
        after = bytes(memory[SATURN_MIDI_68K_STATE_ADDRESS:SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES])
        self.assertEqual(after, before)

    def test_cross_batch_timestamp_regression_fails_before_mutation(self):
        first = tuple(_program(32).records)
        bad = (
            SaturnMidiRecord(31000, SaturnMidiOpcode.NOTE_ON, 0, 60, 100),
        )
        memory = bytearray(_RAM_SIZE)
        image = build_srk_saturn_midi_68k_resident_stream_service_image()
        machine = _Machine(image.words, memory)
        _publish_clock(memory, 32000)
        _publish_batch(memory, 1, first)
        machine.run_until(lambda: _read_word(memory, _MB_READ_SEQUENCE) == 1)
        before = bytes(memory[SATURN_MIDI_68K_STATE_ADDRESS:SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES])

        _publish_batch(memory, 2, bad)
        machine.run_until(
            lambda: _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
            == SATURN_MIDI_68K_STREAM_FLAG_ERROR
        )
        self.assertEqual(
            _read_word(memory, _svc(SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET)),
            SATURN_MIDI_68K_STREAM_ERROR_TIMESTAMP,
        )
        after = bytes(memory[SATURN_MIDI_68K_STATE_ADDRESS:SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES])
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
