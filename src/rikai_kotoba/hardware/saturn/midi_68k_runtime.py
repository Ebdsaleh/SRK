"""Silent runtime orchestration contract for SRK's Saturn MIDI 68K proof.

This module defines and renders the first bounded runtime path that can stop the
Saturn sound CPU, install the already-reviewed protocol-only MC68EC000 image,
publish and verify the deterministic MIDI preload, then restart the sound CPU.
The committed C implementation remains uncalled by the diagnostic shell in this
tranche, so merely adding this module enables no new Saturn runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .midi_mailbox import SATURN_MIDI_MAILBOX_FLAG_READY


SATURN_MIDI_SMPC_COMREG_ADDRESS = 0x2010001F
SATURN_MIDI_SMPC_SF_ADDRESS = 0x20100063
SATURN_MIDI_TVSTAT_ADDRESS = 0x25F80004
SATURN_MIDI_SOUND_RAM_SH2_BASE = 0x25A00000
SATURN_MIDI_SMPC_SNDON = 0x06
SATURN_MIDI_SMPC_SNDOFF = 0x07
SATURN_MIDI_SMPC_TIMEOUT = 1_000_000
SATURN_MIDI_ACK_READ_INDEX = 1
SATURN_MIDI_ACK_READ_SEQUENCE = 1


class SaturnMidi68KRuntimeStatus(IntEnum):
    NOT_STARTED = 0
    SOUND_STOP_FAILED = 1
    INSTALL_FAILED = 2
    PRELOAD_FAILED = 3
    SOUND_START_FAILED = 4
    RUNNING = 5
    ACKNOWLEDGED = 6
    CONSUMER_ERROR = 7


@dataclass(frozen=True)
class SaturnMidi68KProtocolSnapshot:
    flags: int
    read_sequence: int
    read_index: int
    last_error: int

    @property
    def ready(self) -> bool:
        return bool(self.flags & SATURN_MIDI_MAILBOX_FLAG_READY)


def classify_srk_saturn_midi_68k_protocol_snapshot(
    snapshot: SaturnMidi68KProtocolSnapshot,
) -> SaturnMidi68KRuntimeStatus:
    """Classify one non-blocking mailbox snapshot from the silent 68K proof."""

    if snapshot.last_error != 0:
        return SaturnMidi68KRuntimeStatus.CONSUMER_ERROR
    if (
        snapshot.ready
        and snapshot.read_sequence == SATURN_MIDI_ACK_READ_SEQUENCE
        and snapshot.read_index == SATURN_MIDI_ACK_READ_INDEX
    ):
        return SaturnMidi68KRuntimeStatus.ACKNOWLEDGED
    return SaturnMidi68KRuntimeStatus.RUNNING


def render_srk_saturn_midi_68k_runtime_header() -> str:
    """Render the C89 header for the still-uncalled silent protocol runtime."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RUNTIME_H",
            "#define SRK_SATURN_MIDI_68K_RUNTIME_H",
            "",
            "#define SRK_MIDI_68K_RUNTIME_NOT_STARTED 0u",
            "#define SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED 1u",
            "#define SRK_MIDI_68K_RUNTIME_INSTALL_FAILED 2u",
            "#define SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED 3u",
            "#define SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED 4u",
            "#define SRK_MIDI_68K_RUNTIME_RUNNING 5u",
            "#define SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED 6u",
            "#define SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR 7u",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_TELEMETRY {",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "} SRK_SATURN_MIDI_68K_TELEMETRY;",
            "",
            "/* This source tranche defines the path but production does not call it yet. */",
            "unsigned int srk_saturn_midi_68k_protocol_begin(void);",
            "unsigned int srk_saturn_midi_68k_protocol_poll(",
            "    SRK_SATURN_MIDI_68K_TELEMETRY *telemetry",
            ");",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_runtime_source() -> str:
    """Render C89 runtime orchestration with no SCSP register access."""

    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_runtime.h"',
            '#include "srk_saturn_midi_68k_installer.h"',
            '#include "srk_saturn_midi_mailbox.h"',
            '#include "srk_saturn_midi_generated.h"',
            "",
            "#define SRK_MIDI_RUNTIME_SMPC_COMREG (*(volatile unsigned char *)0x2010001FUL)",
            "#define SRK_MIDI_RUNTIME_SMPC_SF     (*(volatile unsigned char *)0x20100063UL)",
            "#define SRK_MIDI_RUNTIME_TVSTAT      (*(volatile unsigned short *)0x25F80004UL)",
            "#define SRK_MIDI_RUNTIME_SOUND_RAM   ((volatile unsigned short *)0x25A00000UL)",
            "",
            "#define SRK_MIDI_RUNTIME_SMPC_SNDON  0x06u",
            "#define SRK_MIDI_RUNTIME_SMPC_SNDOFF 0x07u",
            "#define SRK_MIDI_RUNTIME_SMPC_TIMEOUT 1000000UL",
            "",
            "static int srk_saturn_midi_runtime_wait_smpc_ready(void)",
            "{",
            "    unsigned long remaining;",
            "",
            "    remaining = SRK_MIDI_RUNTIME_SMPC_TIMEOUT;",
            "    while(SRK_MIDI_RUNTIME_SMPC_SF & 0x01u){",
            "        if(remaining == 0UL)",
            "            return 0;",
            "        remaining -= 1UL;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static int srk_saturn_midi_runtime_smpc_command(unsigned char command)",
            "{",
            "    if(!srk_saturn_midi_runtime_wait_smpc_ready())",
            "        return 0;",
            "",
            "    /* Match the already accepted Type-B SMPC command flow. */",
            "    SRK_MIDI_RUNTIME_SMPC_SF = 0x01u;",
            "    SRK_MIDI_RUNTIME_SMPC_COMREG = command;",
            "    return srk_saturn_midi_runtime_wait_smpc_ready();",
            "}",
            "",
            "static void srk_saturn_midi_runtime_wait_command_window(void)",
            "{",
            "    /* The accepted diagnostic waits for V-BLANK-OUT before sound commands. */",
            "    while(SRK_MIDI_RUNTIME_TVSTAT & 0x0008u)",
            "        ;",
            "}",
            "",
            "static unsigned short srk_saturn_midi_runtime_read_word(unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_RUNTIME_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "static int srk_saturn_midi_runtime_verify_preload(void)",
            "{",
            "    const SRK_SATURN_MIDI_EVENT *event;",
            "    unsigned long index;",
            "    unsigned long base;",
            "",
            "    if(!srk_saturn_midi_preload_is_ready())",
            "        return 0;",
            "    if(srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL)) != SRK_MIDI_PRELOAD_WRITE_SEQUENCE)",
            "        return 0;",
            "    if(srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL)) != 0u)",
            "        return 0;",
            "    if(srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL)) != (unsigned short)SRK_MIDI_EVENT_COUNT)",
            "        return 0;",
            "    if(srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL)) != 0u)",
            "        return 0;",
            "    if(srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL)) != 0u)",
            "        return 0;",
            "",
            "    base = SRK_MIDI_TONE_BANK_ADDRESS;",
            "    for(index=0UL; index<(unsigned long)(SRK_MIDI_TONE_COUNT * SRK_MIDI_TONE_SAMPLES); index++){",
            "        if(srk_saturn_midi_runtime_read_word(base + (index * 2UL)) != srk_saturn_midi_tone_bank[index / SRK_MIDI_TONE_SAMPLES][index % SRK_MIDI_TONE_SAMPLES])",
            "            return 0;",
            "    }",
            "",
            "    base = SRK_MIDI_QUEUE_ADDRESS;",
            "    for(index=0UL; index<SRK_MIDI_EVENT_COUNT; index++){",
            "        event = &srk_saturn_midi_events[index];",
            "        if(srk_saturn_midi_runtime_read_word(base + (index * 8UL) + 0UL) != (unsigned short)(event->time_us >> 16))",
            "            return 0;",
            "        if(srk_saturn_midi_runtime_read_word(base + (index * 8UL) + 2UL) != (unsigned short)(event->time_us & 0xFFFFUL))",
            "            return 0;",
            "        if(srk_saturn_midi_runtime_read_word(base + (index * 8UL) + 4UL) != (unsigned short)(((unsigned short)event->opcode << 8) | event->channel))",
            "            return 0;",
            "        if(srk_saturn_midi_runtime_read_word(base + (index * 8UL) + 6UL) != (unsigned short)(((unsigned short)event->data0 << 8) | event->data1))",
            "            return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_protocol_begin(void)",
            "{",
            "    srk_saturn_midi_runtime_wait_command_window();",
            "    if(!srk_saturn_midi_runtime_smpc_command(SRK_MIDI_RUNTIME_SMPC_SNDOFF))",
            "        return SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED;",
            "",
            "    if(!srk_saturn_midi_68k_install_while_stopped())",
            "        return SRK_MIDI_68K_RUNTIME_INSTALL_FAILED;",
            "",
            "    srk_saturn_midi_preload_publish();",
            "    if(!srk_saturn_midi_runtime_verify_preload())",
            "        return SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED;",
            "",
            "    if(!srk_saturn_midi_runtime_smpc_command(SRK_MIDI_RUNTIME_SMPC_SNDON))",
            "        return SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED;",
            "",
            "    return SRK_MIDI_68K_RUNTIME_RUNNING;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_protocol_poll(",
            "    SRK_SATURN_MIDI_68K_TELEMETRY *telemetry",
            ")",
            "{",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "",
            "    flags = srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL));",
            "    read_sequence = srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL));",
            "    read_index = srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL));",
            "    last_error = srk_saturn_midi_runtime_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL));",
            "",
            "    if(telemetry){",
            "        telemetry->flags = flags;",
            "        telemetry->read_sequence = read_sequence;",
            "        telemetry->read_index = read_index;",
            "        telemetry->last_error = last_error;",
            "    }",
            "",
            "    if(last_error != 0u)",
            "        return SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "    if((flags & SRK_MIDI_MAILBOX_FLAG_READY) != 0u &&",
            "       read_sequence == SRK_MIDI_PRELOAD_WRITE_SEQUENCE &&",
            "       read_index == 1u)",
            "        return SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;",
            "    return SRK_MIDI_68K_RUNTIME_RUNNING;",
            "}",
            "",
        )
    )
