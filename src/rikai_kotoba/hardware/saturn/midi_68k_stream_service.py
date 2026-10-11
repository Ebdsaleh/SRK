"""Multi-batch/refill and timestamp-scheduler contract for the Saturn MIDI 68K service.

R21 physically accepted complete dynamic MIDI state mutation on the real
MC68EC000.  This module advances that immutable baseline into a continuous
service contract without touching SCSP playback registers.

The SH-2 producer reuses the accepted 32-record Sound-RAM queue and publishes
successive non-zero 16-bit write sequences.  A new service/control block at
0x1E00 carries continuous-service telemetry plus a producer-owned 32-bit
microsecond clock.  The clock uses an odd/even generation seqlock so the
16-bit sound CPU can reject torn 32-bit reads.

This module is host-side/model code only.  It performs no hardware I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_AUDIO_BOUNDARY,
    SATURN_MIDI_68K_CHANNEL_COUNT,
    SaturnMidi68KChannelState,
    _consume_record,
    default_saturn_midi_68k_channel_state,
    validate_srk_saturn_midi_68k_command_layout,
)
from .midi_bridge import SATURN_MIDI_QUEUE_CAPACITY
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS = 0x00001E00
SATURN_MIDI_68K_STREAM_SERVICE_BYTES = 0x00000200
SATURN_MIDI_68K_STREAM_SERVICE_END = (
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS + SATURN_MIDI_68K_STREAM_SERVICE_BYTES
)

SATURN_MIDI_68K_STREAM_SERVICE_MAGIC = 0x4D53  # "MS"
SATURN_MIDI_68K_STREAM_SERVICE_VERSION = 1

SATURN_MIDI_68K_STREAM_FLAG_RUNNING = 0x0001
SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH = 0x0002
SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME = 0x0004
SATURN_MIDI_68K_STREAM_FLAG_ERROR = 0x0008

SATURN_MIDI_68K_STREAM_ERROR_NONE = 0
SATURN_MIDI_68K_STREAM_ERROR_MAGIC = 1
SATURN_MIDI_68K_STREAM_ERROR_VERSION = 2
SATURN_MIDI_68K_STREAM_ERROR_CONTRACT = 3
SATURN_MIDI_68K_STREAM_ERROR_EMPTY = 4
SATURN_MIDI_68K_STREAM_ERROR_COUNT = 6
SATURN_MIDI_68K_STREAM_ERROR_RECORD = 7
SATURN_MIDI_68K_STREAM_ERROR_SEQUENCE = 8
SATURN_MIDI_68K_STREAM_ERROR_TIMESTAMP = 9

# Byte offsets inside the 0x1E00 service block.
SATURN_MIDI_68K_STREAM_MAGIC_OFFSET = 0
SATURN_MIDI_68K_STREAM_VERSION_OFFSET = 2
SATURN_MIDI_68K_STREAM_FLAGS_OFFSET = 4
SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET = 6
SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET = 8
SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET = 10
SATURN_MIDI_68K_STREAM_CURRENT_SEQUENCE_OFFSET = 12
SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET = 14
SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET = 16
SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET = 18
SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET = 20
SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET = 22
SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET = 24
SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET = 26
SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET = 28
SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET = 30
SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET = 32
SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET = 34
SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET = 36


class SaturnMidi68KStreamServiceError(RuntimeError):
    """Raised when a multi-batch stream violates the reviewed service contract."""


@dataclass(frozen=True)
class SaturnMidi68KStreamBatch:
    sequence: int
    records: tuple[SaturnMidiRecord, ...]

    @property
    def final_time_us(self) -> int:
        return self.records[-1].time_us


@dataclass(frozen=True)
class SaturnMidi68KStreamSnapshot:
    now_us: int
    channels: tuple[SaturnMidi68KChannelState, ...]
    acknowledged_sequence: int
    read_index: int
    batch_count: int
    total_processed_records: int
    last_due_time_us: int
    next_due_time_us: int | None
    waiting_for_batch: bool
    waiting_for_time: bool
    last_error: int


def validate_srk_saturn_midi_68k_stream_layout() -> None:
    """Prove the service block fills only the reviewed pre-audio gap."""

    validate_srk_saturn_midi_68k_command_layout()
    if SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS != 0x00001E00:
        raise SaturnMidi68KStreamServiceError("stream service no longer begins at 0x1E00")
    if SATURN_MIDI_68K_STREAM_SERVICE_END != SATURN_MIDI_68K_AUDIO_BOUNDARY:
        raise SaturnMidi68KStreamServiceError(
            "stream service block no longer ends exactly at the 0x2000 audio boundary"
        )
    highest_offset = SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET + 2
    if highest_offset > SATURN_MIDI_68K_STREAM_SERVICE_BYTES:
        raise SaturnMidi68KStreamServiceError("stream service fields exceed reserved block")


def next_saturn_midi_stream_sequence(sequence: int) -> int:
    """Return the strict next non-zero 16-bit producer sequence."""

    if sequence < 0 or sequence > 0xFFFF:
        raise SaturnMidi68KStreamServiceError("stream sequence is outside 16-bit range")
    value = (sequence + 1) & 0xFFFF
    return 1 if value == 0 else value


def _validate_stream_record(record: SaturnMidiRecord, previous_time: int) -> None:
    if record.time_us < previous_time:
        raise SaturnMidi68KStreamServiceError(
            "stream timestamps must remain chronological across refill boundaries"
        )
    if record.time_us < 0 or record.time_us > 0xFFFFFFFF:
        raise SaturnMidi68KStreamServiceError("stream timestamp exceeds 32-bit range")
    if not isinstance(record.opcode, SaturnMidiOpcode):
        raise SaturnMidi68KStreamServiceError("stream contains an invalid SRKM opcode")
    if record.channel < 0 or record.channel >= SATURN_MIDI_68K_CHANNEL_COUNT:
        raise SaturnMidi68KStreamServiceError("stream contains an invalid MIDI channel")
    if record.data0 < 0 or record.data0 > 0x7F:
        raise SaturnMidi68KStreamServiceError("stream data0 is outside MIDI 7-bit range")
    if record.data1 < 0 or record.data1 > 0x7F:
        raise SaturnMidi68KStreamServiceError("stream data1 is outside MIDI 7-bit range")


def build_srk_saturn_midi_stream_batches(
    program: SaturnMidiProgram,
) -> tuple[SaturnMidi68KStreamBatch, ...]:
    """Partition one chronological SRKM program into strict 32-record refills."""

    validate_srk_saturn_midi_68k_stream_layout()
    if not program.records:
        raise SaturnMidi68KStreamServiceError("stream service requires at least one record")

    previous_time = -1
    for record in program.records:
        _validate_stream_record(record, previous_time)
        previous_time = record.time_us

    batches: list[SaturnMidi68KStreamBatch] = []
    sequence = 1
    for start in range(0, len(program.records), SATURN_MIDI_QUEUE_CAPACITY):
        records = tuple(program.records[start : start + SATURN_MIDI_QUEUE_CAPACITY])
        batches.append(SaturnMidi68KStreamBatch(sequence=sequence, records=records))
        sequence = next_saturn_midi_stream_sequence(sequence)
    return tuple(batches)


def validate_srk_saturn_midi_stream_batches(
    batches: tuple[SaturnMidi68KStreamBatch, ...],
) -> None:
    """Validate strict sequence/count/timestamp continuity across producer refills."""

    validate_srk_saturn_midi_68k_stream_layout()
    if not batches:
        raise SaturnMidi68KStreamServiceError("stream requires at least one batch")

    expected_sequence = 1
    previous_time = -1
    for batch in batches:
        if batch.sequence != expected_sequence:
            raise SaturnMidi68KStreamServiceError(
                f"expected stream sequence {expected_sequence} but received {batch.sequence}"
            )
        if not batch.records:
            raise SaturnMidi68KStreamServiceError("stream batch cannot be empty")
        if len(batch.records) > SATURN_MIDI_QUEUE_CAPACITY:
            raise SaturnMidi68KStreamServiceError("stream batch exceeds queue capacity")
        for record in batch.records:
            _validate_stream_record(record, previous_time)
            previous_time = record.time_us
        expected_sequence = next_saturn_midi_stream_sequence(expected_sequence)


def _snapshot(
    *,
    now_us: int,
    channels: list[SaturnMidi68KChannelState],
    acknowledged_sequence: int,
    read_index: int,
    batch_count: int,
    total_processed_records: int,
    last_due_time_us: int,
    next_due_time_us: int | None,
    waiting_for_batch: bool,
    waiting_for_time: bool,
) -> SaturnMidi68KStreamSnapshot:
    return SaturnMidi68KStreamSnapshot(
        now_us=now_us,
        channels=tuple(channels),
        acknowledged_sequence=acknowledged_sequence,
        read_index=read_index,
        batch_count=batch_count,
        total_processed_records=total_processed_records,
        last_due_time_us=last_due_time_us,
        next_due_time_us=next_due_time_us,
        waiting_for_batch=waiting_for_batch,
        waiting_for_time=waiting_for_time,
        last_error=SATURN_MIDI_68K_STREAM_ERROR_NONE,
    )


def simulate_srk_saturn_midi_stream_timeline(
    program: SaturnMidiProgram,
    clock_updates_us: tuple[int, ...],
) -> tuple[SaturnMidi68KStreamSnapshot, ...]:
    """Model resident refill + timestamp gating at successive producer clock updates.

    A refill is not acknowledged until every record in that batch has become due
    and has been applied.  The next refill therefore cannot become visible to the
    resident consumer early.  State persists across every acknowledged batch.
    """

    batches = build_srk_saturn_midi_stream_batches(program)
    if not clock_updates_us:
        raise SaturnMidi68KStreamServiceError("stream simulation requires clock updates")
    previous_clock = -1
    for value in clock_updates_us:
        if value < 0 or value > 0xFFFFFFFF:
            raise SaturnMidi68KStreamServiceError("published stream clock exceeds 32-bit range")
        if value < previous_clock:
            raise SaturnMidi68KStreamServiceError("published stream clock must be monotonic")
        previous_clock = value

    channels = [default_saturn_midi_68k_channel_state() for _ in range(SATURN_MIDI_68K_CHANNEL_COUNT)]
    batch_slot = 0
    record_slot = 0
    acknowledged_sequence = 0
    read_index = 0
    batch_count = 0
    total_processed = 0
    last_due = 0
    snapshots: list[SaturnMidi68KStreamSnapshot] = []

    for now_us in clock_updates_us:
        while batch_slot < len(batches):
            batch = batches[batch_slot]
            while record_slot < len(batch.records):
                record = batch.records[record_slot]
                if record.time_us > now_us:
                    break
                channels[record.channel] = _consume_record(channels[record.channel], record)
                record_slot += 1
                read_index = record_slot
                total_processed += 1
                last_due = record.time_us

            if record_slot != len(batch.records):
                break

            acknowledged_sequence = batch.sequence
            read_index = len(batch.records)
            batch_count += 1
            batch_slot += 1
            record_slot = 0
            if batch_slot < len(batches):
                read_index = 0
                continue
            break

        if batch_slot >= len(batches):
            next_due = None
            waiting_for_batch = True
            waiting_for_time = False
        else:
            batch = batches[batch_slot]
            next_due = batch.records[record_slot].time_us
            waiting_for_batch = False
            waiting_for_time = next_due > now_us

        snapshots.append(
            _snapshot(
                now_us=now_us,
                channels=channels,
                acknowledged_sequence=acknowledged_sequence,
                read_index=read_index,
                batch_count=batch_count,
                total_processed_records=total_processed,
                last_due_time_us=last_due,
                next_due_time_us=next_due,
                waiting_for_batch=waiting_for_batch,
                waiting_for_time=waiting_for_time,
            )
        )

    return tuple(snapshots)


def render_srk_saturn_midi_68k_stream_service_header() -> str:
    """Render the C89 SH-2 producer-facing stream/refill/timebase contract."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_STREAM_SERVICE_H",
            "#define SRK_SATURN_MIDI_68K_STREAM_SERVICE_H",
            "",
            "#include \"srk_saturn_midi_generated.h\"",
            "",
            f"#define SRK_MIDI_68K_STREAM_SERVICE_ADDRESS 0x{SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_STREAM_SERVICE_BYTES 0x{SATURN_MIDI_68K_STREAM_SERVICE_BYTES:08X}UL",
            f"#define SRK_MIDI_68K_STREAM_MAGIC 0x{SATURN_MIDI_68K_STREAM_SERVICE_MAGIC:04X}u",
            f"#define SRK_MIDI_68K_STREAM_VERSION {SATURN_MIDI_68K_STREAM_SERVICE_VERSION}u",
            f"#define SRK_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET {SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET}u",
            f"#define SRK_MIDI_68K_STREAM_CLOCK_HI_OFFSET {SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET}u",
            f"#define SRK_MIDI_68K_STREAM_CLOCK_LO_OFFSET {SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET}u",
            "",
            "void srk_saturn_midi_stream_clock_publish(unsigned long now_us);",
            "int srk_saturn_midi_stream_batch_publish(const SRK_SATURN_MIDI_EVENT *events, unsigned short count, unsigned short sequence);",
            "int srk_saturn_midi_stream_batch_acknowledged(unsigned short sequence);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_stream_service_source() -> str:
    """Render C89 SH-2 producer helpers; nothing invokes them automatically."""

    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_stream_service.h"',
            '#include "srk_saturn_midi_mailbox.h"',
            "",
            "#define SRK_MIDI_STREAM_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
            "",
            "static void srk_midi_stream_write(unsigned long address, unsigned short value)",
            "{",
            "    SRK_MIDI_STREAM_SOUND_RAM[address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_midi_stream_read(unsigned long address)",
            "{",
            "    return SRK_MIDI_STREAM_SOUND_RAM[address >> 1];",
            "}",
            "",
            "void srk_saturn_midi_stream_clock_publish(unsigned long now_us)",
            "{",
            "    unsigned long base;",
            "    unsigned short generation;",
            "",
            "    base = SRK_MIDI_68K_STREAM_SERVICE_ADDRESS;",
            "    generation = srk_midi_stream_read(base + SRK_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET);",
            "    generation = (unsigned short)(generation + 1u);",
            "    if((generation & 1u) == 0u)",
            "        generation = (unsigned short)(generation + 1u);",
            "    srk_midi_stream_write(base + SRK_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET, generation);",
            "    srk_midi_stream_write(base + SRK_MIDI_68K_STREAM_CLOCK_HI_OFFSET, (unsigned short)(now_us >> 16));",
            "    srk_midi_stream_write(base + SRK_MIDI_68K_STREAM_CLOCK_LO_OFFSET, (unsigned short)(now_us & 0xFFFFUL));",
            "    srk_midi_stream_write(base + SRK_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET, (unsigned short)(generation + 1u));",
            "}",
            "",
            "int srk_saturn_midi_stream_batch_publish(const SRK_SATURN_MIDI_EVENT *events, unsigned short count, unsigned short sequence)",
            "{",
            "    unsigned short index;",
            "    unsigned short flags;",
            "    unsigned short write_sequence;",
            "    unsigned short read_sequence;",
            "    unsigned short expected_sequence;",
            "    const SRK_SATURN_MIDI_EVENT *event;",
            "",
            "    if(events == 0 || count == 0u || count > SRK_MIDI_QUEUE_CAPACITY || sequence == 0u)",
            "        return 0;",
            "",
            "    flags = srk_midi_stream_read(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL));",
            "    write_sequence = srk_midi_stream_read(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL));",
            "    read_sequence = srk_midi_stream_read(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL));",
            "    if((flags & SRK_MIDI_MAILBOX_FLAG_READY) != 0u && write_sequence != read_sequence)",
            "        return 0;",
            "    expected_sequence = (unsigned short)(read_sequence + 1u);",
            "    if(expected_sequence == 0u)",
            "        expected_sequence = 1u;",
            "    if(sequence != expected_sequence)",
            "        return 0;",
            "",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL), 0u);",
            "    for(index=0u; index<count; index++){",
            "        event = &events[index];",
            "        srk_midi_stream_write(SRK_MIDI_QUEUE_ADDRESS + ((unsigned long)index * 8UL) + 0UL, (unsigned short)(event->time_us >> 16));",
            "        srk_midi_stream_write(SRK_MIDI_QUEUE_ADDRESS + ((unsigned long)index * 8UL) + 2UL, (unsigned short)(event->time_us & 0xFFFFUL));",
            "        srk_midi_stream_write(SRK_MIDI_QUEUE_ADDRESS + ((unsigned long)index * 8UL) + 4UL, (unsigned short)(((unsigned short)event->opcode << 8) | event->channel));",
            "        srk_midi_stream_write(SRK_MIDI_QUEUE_ADDRESS + ((unsigned long)index * 8UL) + 6UL, (unsigned short)(((unsigned short)event->data0 << 8) | event->data1));",
            "    }",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL), SRK_MIDI_MAILBOX_MAGIC0);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL), SRK_MIDI_MAILBOX_MAGIC1);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL), SRK_MIDI_MAILBOX_VERSION);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL), sequence);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL), count);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL), SRK_MIDI_QUEUE_CAPACITY);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), count);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL), 0u);",
            "    srk_midi_stream_write(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL), SRK_MIDI_MAILBOX_FLAG_READY);",
            "    return 1;",
            "}",
            "",
            "int srk_saturn_midi_stream_batch_acknowledged(unsigned short sequence)",
            "{",
            "    return srk_midi_stream_read(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL)) == sequence;",
            "}",
            "",
        )
    )
