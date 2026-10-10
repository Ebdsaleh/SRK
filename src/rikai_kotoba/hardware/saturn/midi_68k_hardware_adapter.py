"""Reviewed Saturn hardware adapter for SRK's silent MIDI MC68EC000 proof.

This module binds the already-accepted Saturn SMPC/Sound-RAM behavior to the
adapter-neutral runtime operation table.  It deliberately does not call the
runtime orchestrator and does not touch SCSP registers.  The committed C adapter
therefore remains inert until a later, separately gated diagnostic control path
passes it to the runtime layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_runtime import (
    SATURN_MIDI_SMPC_COMREG_ADDRESS,
    SATURN_MIDI_SMPC_SF_ADDRESS,
    SATURN_MIDI_TVSTAT_ADDRESS,
    SATURN_MIDI_SOUND_RAM_SH2_BASE,
    SATURN_MIDI_SMPC_SNDON,
    SATURN_MIDI_SMPC_SNDOFF,
    SATURN_MIDI_SMPC_TIMEOUT,
)


@dataclass(frozen=True)
class SaturnMidi68KHardwareAdapterContract:
    smpc_comreg_address: int
    smpc_sf_address: int
    tvstat_address: int
    sound_ram_base: int
    sndon_command: int
    sndoff_command: int
    smpc_timeout: int


def build_srk_saturn_midi_68k_hardware_adapter_contract() -> SaturnMidi68KHardwareAdapterContract:
    """Return the already-accepted Saturn hardware constants used by the adapter."""

    contract = SaturnMidi68KHardwareAdapterContract(
        smpc_comreg_address=SATURN_MIDI_SMPC_COMREG_ADDRESS,
        smpc_sf_address=SATURN_MIDI_SMPC_SF_ADDRESS,
        tvstat_address=SATURN_MIDI_TVSTAT_ADDRESS,
        sound_ram_base=SATURN_MIDI_SOUND_RAM_SH2_BASE,
        sndon_command=SATURN_MIDI_SMPC_SNDON,
        sndoff_command=SATURN_MIDI_SMPC_SNDOFF,
        smpc_timeout=SATURN_MIDI_SMPC_TIMEOUT,
    )
    if contract.smpc_comreg_address != 0x2010001F:
        raise RuntimeError("Saturn MIDI SMPC COMREG address changed unexpectedly")
    if contract.smpc_sf_address != 0x20100063:
        raise RuntimeError("Saturn MIDI SMPC SF address changed unexpectedly")
    if contract.tvstat_address != 0x25F80004:
        raise RuntimeError("Saturn MIDI VDP2 TVSTAT address changed unexpectedly")
    if contract.sound_ram_base != 0x25A00000:
        raise RuntimeError("Saturn MIDI Sound-RAM aperture changed unexpectedly")
    if contract.sndon_command != 0x06 or contract.sndoff_command != 0x07:
        raise RuntimeError("Saturn MIDI sound-CPU SMPC commands changed unexpectedly")
    if contract.smpc_timeout != 1_000_000:
        raise RuntimeError("Saturn MIDI SMPC timeout changed unexpectedly")
    return contract


def render_srk_saturn_midi_68k_hardware_adapter_header() -> str:
    """Render the C89 header for the still-uncalled Saturn hardware adapter."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_HARDWARE_ADAPTER_H",
            "#define SRK_SATURN_MIDI_68K_HARDWARE_ADAPTER_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            "",
            "/* Adapter exists, but production does not pass it to the runtime yet. */",
            "const SRK_SATURN_MIDI_68K_RUNTIME_OPS *",
            "srk_saturn_midi_68k_hardware_adapter_ops(void);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_hardware_adapter_source() -> str:
    """Render the C89 adapter using only the already-accepted Saturn flow."""

    contract = build_srk_saturn_midi_68k_hardware_adapter_contract()
    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_hardware_adapter.h"',
            '#include "srk_saturn_midi_68k_installer.h"',
            '#include "srk_saturn_midi_mailbox.h"',
            '#include "srk_saturn_midi_generated.h"',
            "",
            f"#define SRK_MIDI_ADAPTER_SMPC_COMREG (*(volatile unsigned char *)0x{contract.smpc_comreg_address:08X}UL)",
            f"#define SRK_MIDI_ADAPTER_SMPC_SF     (*(volatile unsigned char *)0x{contract.smpc_sf_address:08X}UL)",
            f"#define SRK_MIDI_ADAPTER_TVSTAT      (*(volatile unsigned short *)0x{contract.tvstat_address:08X}UL)",
            f"#define SRK_MIDI_ADAPTER_SOUND_RAM   ((volatile unsigned short *)0x{contract.sound_ram_base:08X}UL)",
            "",
            f"#define SRK_MIDI_ADAPTER_SMPC_SNDON  0x{contract.sndon_command:02X}u",
            f"#define SRK_MIDI_ADAPTER_SMPC_SNDOFF 0x{contract.sndoff_command:02X}u",
            f"#define SRK_MIDI_ADAPTER_SMPC_TIMEOUT {contract.smpc_timeout}UL",
            "",
            "static int srk_saturn_midi_adapter_wait_smpc_ready(void)",
            "{",
            "    unsigned long remaining;",
            "",
            "    remaining = SRK_MIDI_ADAPTER_SMPC_TIMEOUT;",
            "    while(SRK_MIDI_ADAPTER_SMPC_SF & 0x01u){",
            "        if(remaining == 0UL)",
            "            return 0;",
            "        remaining -= 1UL;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static int srk_saturn_midi_adapter_smpc_command(unsigned char command)",
            "{",
            "    if(!srk_saturn_midi_adapter_wait_smpc_ready())",
            "        return 0;",
            "",
            "    /* Same accepted Sega Type-B flow as standalone Audio Stage 1-6. */",
            "    SRK_MIDI_ADAPTER_SMPC_SF = 0x01u;",
            "    SRK_MIDI_ADAPTER_SMPC_COMREG = command;",
            "    return srk_saturn_midi_adapter_wait_smpc_ready();",
            "}",
            "",
            "static void srk_saturn_midi_adapter_wait_command_window(void)",
            "{",
            "    /* Match the accepted diagnostic: wait from V-BLANK-IN to V-BLANK-OUT. */",
            "    while(SRK_MIDI_ADAPTER_TVSTAT & 0x0008u)",
            "        ;",
            "}",
            "",
            "static unsigned short srk_saturn_midi_adapter_read_sound_word(unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_ADAPTER_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "static int srk_saturn_midi_adapter_stop_sound_cpu(void)",
            "{",
            "    srk_saturn_midi_adapter_wait_command_window();",
            "    return srk_saturn_midi_adapter_smpc_command(SRK_MIDI_ADAPTER_SMPC_SNDOFF);",
            "}",
            "",
            "static int srk_saturn_midi_adapter_install_program(void)",
            "{",
            "    return srk_saturn_midi_68k_install_while_stopped();",
            "}",
            "",
            "static void srk_saturn_midi_adapter_publish_preload(void)",
            "{",
            "    srk_saturn_midi_preload_publish();",
            "}",
            "",
            "static int srk_saturn_midi_adapter_verify_preload(void)",
            "{",
            "    const SRK_SATURN_MIDI_EVENT *event;",
            "    unsigned long index;",
            "    unsigned long base;",
            "",
            "    if(!srk_saturn_midi_preload_is_ready())",
            "        return 0;",
            "    if(srk_saturn_midi_adapter_read_sound_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL)) != SRK_MIDI_PRELOAD_WRITE_SEQUENCE)",
            "        return 0;",
            "    if(srk_saturn_midi_adapter_read_sound_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL)) != 0u)",
            "        return 0;",
            "    if(srk_saturn_midi_adapter_read_sound_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL)) != (unsigned short)SRK_MIDI_EVENT_COUNT)",
            "        return 0;",
            "    if(srk_saturn_midi_adapter_read_sound_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL)) != 0u)",
            "        return 0;",
            "    if(srk_saturn_midi_adapter_read_sound_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL)) != 0u)",
            "        return 0;",
            "",
            "    base = SRK_MIDI_TONE_BANK_ADDRESS;",
            "    for(index=0UL; index<(unsigned long)(SRK_MIDI_TONE_COUNT * SRK_MIDI_TONE_SAMPLES); index++){",
            "        if(srk_saturn_midi_adapter_read_sound_word(base + (index * 2UL)) != srk_saturn_midi_tone_bank[index / SRK_MIDI_TONE_SAMPLES][index % SRK_MIDI_TONE_SAMPLES])",
            "            return 0;",
            "    }",
            "",
            "    base = SRK_MIDI_QUEUE_ADDRESS;",
            "    for(index=0UL; index<SRK_MIDI_EVENT_COUNT; index++){",
            "        event = &srk_saturn_midi_events[index];",
            "        if(srk_saturn_midi_adapter_read_sound_word(base + (index * 8UL) + 0UL) != (unsigned short)(event->time_us >> 16))",
            "            return 0;",
            "        if(srk_saturn_midi_adapter_read_sound_word(base + (index * 8UL) + 2UL) != (unsigned short)(event->time_us & 0xFFFFUL))",
            "            return 0;",
            "        if(srk_saturn_midi_adapter_read_sound_word(base + (index * 8UL) + 4UL) != (unsigned short)(((unsigned short)event->opcode << 8) | event->channel))",
            "            return 0;",
            "        if(srk_saturn_midi_adapter_read_sound_word(base + (index * 8UL) + 6UL) != (unsigned short)(((unsigned short)event->data0 << 8) | event->data1))",
            "            return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static int srk_saturn_midi_adapter_start_sound_cpu(void)",
            "{",
            "    return srk_saturn_midi_adapter_smpc_command(SRK_MIDI_ADAPTER_SMPC_SNDON);",
            "}",
            "",
            "static unsigned short srk_saturn_midi_adapter_read_mailbox_word(unsigned int word_index)",
            "{",
            "    return srk_saturn_midi_adapter_read_sound_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + ((unsigned long)word_index * 2UL)",
            "    );",
            "}",
            "",
            "static const SRK_SATURN_MIDI_68K_RUNTIME_OPS srk_saturn_midi_adapter_ops = {",
            "    srk_saturn_midi_adapter_stop_sound_cpu,",
            "    srk_saturn_midi_adapter_install_program,",
            "    srk_saturn_midi_adapter_publish_preload,",
            "    srk_saturn_midi_adapter_verify_preload,",
            "    srk_saturn_midi_adapter_start_sound_cpu,",
            "    srk_saturn_midi_adapter_read_mailbox_word",
            "};",
            "",
            "const SRK_SATURN_MIDI_68K_RUNTIME_OPS *",
            "srk_saturn_midi_68k_hardware_adapter_ops(void)",
            "{",
            "    return &srk_saturn_midi_adapter_ops;",
            "}",
            "",
        )
    )
