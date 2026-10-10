"""Silent runtime-orchestration contract for SRK's Saturn MIDI 68K proof.

This module locks the order and telemetry of the first runtime protocol proof
without binding that proof directly to Saturn MMIO.  The committed C layer is a
small operation-table orchestrator: a later, separately reviewed hardware
adapter will supply the already-accepted SMPC stop/start behavior, bounded 68K
installer, preload publisher/verifier and mailbox reads.

Nothing in the production diagnostic calls this layer yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .midi_mailbox import SATURN_MIDI_MAILBOX_FLAG_READY


# Accepted Saturn anchors reserved for the later hardware adapter review.
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
    """Render the C89 header for the still-uncalled orchestration layer."""

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
            "typedef struct SRK_SATURN_MIDI_68K_RUNTIME_OPS {",
            "    int (*stop_sound_cpu)(void);",
            "    int (*install_program)(void);",
            "    void (*publish_preload)(void);",
            "    int (*verify_preload)(void);",
            "    int (*start_sound_cpu)(void);",
            "    unsigned short (*read_mailbox_word)(unsigned int word_index);",
            "} SRK_SATURN_MIDI_68K_RUNTIME_OPS;",
            "",
            "/* Production does not provide or call a hardware adapter in this tranche. */",
            "unsigned int srk_saturn_midi_68k_protocol_begin(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops",
            ");",
            "unsigned int srk_saturn_midi_68k_protocol_poll(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops,",
            "    SRK_SATURN_MIDI_68K_TELEMETRY *telemetry",
            ");",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_runtime_source() -> str:
    """Render C89 sequencing logic with no direct Saturn MMIO."""

    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_runtime.h"',
            '#include "srk_saturn_midi_generated.h"',
            '#include "srk_saturn_midi_mailbox.h"',
            "",
            "static int srk_saturn_midi_68k_runtime_ops_valid(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops",
            ")",
            "{",
            "    return ops &&",
            "        ops->stop_sound_cpu &&",
            "        ops->install_program &&",
            "        ops->publish_preload &&",
            "        ops->verify_preload &&",
            "        ops->start_sound_cpu &&",
            "        ops->read_mailbox_word;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_protocol_begin(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops",
            ")",
            "{",
            "    if(!srk_saturn_midi_68k_runtime_ops_valid(ops))",
            "        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(!ops->stop_sound_cpu())",
            "        return SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED;",
            "    if(!ops->install_program())",
            "        return SRK_MIDI_68K_RUNTIME_INSTALL_FAILED;",
            "",
            "    ops->publish_preload();",
            "    if(!ops->verify_preload())",
            "        return SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED;",
            "    if(!ops->start_sound_cpu())",
            "        return SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED;",
            "    return SRK_MIDI_68K_RUNTIME_RUNNING;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_protocol_poll(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops,",
            "    SRK_SATURN_MIDI_68K_TELEMETRY *telemetry",
            ")",
            "{",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "",
            "    if(!srk_saturn_midi_68k_runtime_ops_valid(ops))",
            "        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "",
            "    flags = ops->read_mailbox_word(SRK_MIDI_MB_FLAGS);",
            "    read_sequence = ops->read_mailbox_word(SRK_MIDI_MB_READ_SEQUENCE);",
            "    read_index = ops->read_mailbox_word(SRK_MIDI_MB_READ_INDEX);",
            "    last_error = ops->read_mailbox_word(SRK_MIDI_MB_LAST_ERROR);",
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
