"""Bounded, non-launching installer for SRK's protocol-only Saturn MIDI 68K image.

This module owns the exact Sound-RAM installation contract for the already
reviewed MC68EC000 program.  It renders C89 source that can copy the program and
reset SSP/PC vectors while the sound CPU is stopped, then verify those writes.

It intentionally does not stop or start the sound CPU, issue SMPC commands,
publish the MIDI mailbox, access SCSP registers, or launch the MC68EC000.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_68k_consumer import (
    SATURN_MIDI_68K_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_STACK_ADDRESS,
    build_srk_saturn_midi_68k_consumer_image,
)
from .midi_bridge import SATURN_MIDI_MAILBOX_ADDRESS, SATURN_SOUND_RAM_BYTES


SATURN_MIDI_68K_RESET_SSP_VECTOR_ADDRESS = 0x00000000
SATURN_MIDI_68K_RESET_PC_VECTOR_ADDRESS = 0x00000004
SATURN_MIDI_68K_VECTOR_TABLE_BYTES = 0x00000400
SATURN_MIDI_68K_DUMMY_LOOP_ADDRESS = 0x00000400
SATURN_MIDI_68K_DUMMY_LOOP_BYTES = 2
SATURN_MIDI_68K_SH2_SOUND_RAM_BASE = 0x25A00000


class SaturnMidi68KInstallerError(RuntimeError):
    """Raised when the bounded 68K installation contract is invalid."""


@dataclass(frozen=True)
class SaturnMidi68KInstallImage:
    program_address: int
    stack_address: int
    program_words: tuple[int, ...]

    @property
    def program_byte_size(self) -> int:
        return len(self.program_words) * 2

    @property
    def program_end_address(self) -> int:
        return self.program_address + self.program_byte_size

    @property
    def program_sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.program_words)
        return sha256(payload).hexdigest()


def build_srk_saturn_midi_68k_install_image() -> SaturnMidi68KInstallImage:
    """Return and validate the deterministic program/vector install image."""

    consumer = build_srk_saturn_midi_68k_consumer_image()
    image = SaturnMidi68KInstallImage(
        program_address=SATURN_MIDI_68K_PROGRAM_ADDRESS,
        stack_address=SATURN_MIDI_68K_STACK_ADDRESS,
        program_words=consumer.words,
    )

    if image.program_address & 1:
        raise SaturnMidi68KInstallerError("68K program address must be word aligned")
    if image.program_address < SATURN_MIDI_68K_DUMMY_LOOP_ADDRESS + SATURN_MIDI_68K_DUMMY_LOOP_BYTES:
        raise SaturnMidi68KInstallerError("68K program overlaps vectors or accepted dummy loop")
    if image.program_end_address > SATURN_MIDI_MAILBOX_ADDRESS:
        raise SaturnMidi68KInstallerError("68K program overlaps the MIDI mailbox")
    if image.program_end_address > SATURN_SOUND_RAM_BYTES:
        raise SaturnMidi68KInstallerError("68K program exceeds Saturn Sound RAM")
    if image.stack_address <= image.program_end_address or image.stack_address >= SATURN_SOUND_RAM_BYTES:
        raise SaturnMidi68KInstallerError("68K stack pointer is outside the reviewed free region")
    if image.stack_address & 1:
        raise SaturnMidi68KInstallerError("68K stack pointer must be word aligned")
    if SATURN_MIDI_68K_RESET_SSP_VECTOR_ADDRESS != 0 or SATURN_MIDI_68K_RESET_PC_VECTOR_ADDRESS != 4:
        raise SaturnMidi68KInstallerError("68K reset vector addresses changed unexpectedly")
    if SATURN_MIDI_68K_VECTOR_TABLE_BYTES != 0x400:
        raise SaturnMidi68KInstallerError("68K vector-table size changed unexpectedly")

    return image


def render_srk_saturn_midi_68k_installer_header() -> str:
    """Render the C89 header for the still-uncalled bounded installer."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_INSTALLER_H",
            "#define SRK_SATURN_MIDI_68K_INSTALLER_H",
            "",
            "/* Caller precondition: MC68EC000 is stopped. This API never launches it. */",
            f"#define SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS 0x{SATURN_MIDI_68K_RESET_SSP_VECTOR_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS 0x{SATURN_MIDI_68K_RESET_PC_VECTOR_ADDRESS:08X}UL",
            "",
            "int srk_saturn_midi_68k_install_while_stopped(void);",
            "int srk_saturn_midi_68k_verify_install(void);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_installer_source() -> str:
    """Render C89 Sound-RAM copy/verify code without SMPC or SCSP actions."""

    build_srk_saturn_midi_68k_install_image()
    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_installer.h"',
            '#include "srk_saturn_midi_68k_program.h"',
            "",
            f"#define SRK_MIDI_68K_SOUND_RAM ((volatile unsigned short *)0x{SATURN_MIDI_68K_SH2_SOUND_RAM_BASE:08X}UL)",
            "",
            "static void srk_saturn_midi_68k_write_word(unsigned long byte_address, unsigned short value)",
            "{",
            "    SRK_MIDI_68K_SOUND_RAM[byte_address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_saturn_midi_68k_read_word(unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_68K_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "static void srk_saturn_midi_68k_write_long(unsigned long byte_address, unsigned long value)",
            "{",
            "    srk_saturn_midi_68k_write_word(byte_address, (unsigned short)(value >> 16));",
            "    srk_saturn_midi_68k_write_word(byte_address + 2UL, (unsigned short)(value & 0xFFFFUL));",
            "}",
            "",
            "static unsigned long srk_saturn_midi_68k_read_long(unsigned long byte_address)",
            "{",
            "    unsigned long high_word;",
            "    unsigned long low_word;",
            "",
            "    high_word = (unsigned long)srk_saturn_midi_68k_read_word(byte_address);",
            "    low_word = (unsigned long)srk_saturn_midi_68k_read_word(byte_address + 2UL);",
            "    return (high_word << 16) | low_word;",
            "}",
            "",
            "int srk_saturn_midi_68k_verify_install(void)",
            "{",
            "    unsigned long index;",
            "",
            "    if(srk_saturn_midi_68k_read_long(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS) != SRK_MIDI_68K_STACK_ADDRESS)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_read_long(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS) != SRK_MIDI_68K_PROGRAM_ADDRESS)",
            "        return 0;",
            "",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_PROGRAM_WORD_COUNT; index++){",
            "        if(srk_saturn_midi_68k_read_word(SRK_MIDI_68K_PROGRAM_ADDRESS + (index * 2UL)) != srk_saturn_midi_68k_program[index])",
            "            return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "int srk_saturn_midi_68k_install_while_stopped(void)",
            "{",
            "    unsigned long index;",
            "",
            "    /* Program first; publish reset vectors only after the complete image exists. */",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_PROGRAM_WORD_COUNT; index++)",
            "        srk_saturn_midi_68k_write_word(",
            "            SRK_MIDI_68K_PROGRAM_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_program[index]",
            "        );",
            "",
            "    srk_saturn_midi_68k_write_long(",
            "        SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,",
            "        SRK_MIDI_68K_STACK_ADDRESS",
            "    );",
            "    srk_saturn_midi_68k_write_long(",
            "        SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,",
            "        SRK_MIDI_68K_PROGRAM_ADDRESS",
            "    );",
            "",
            "    return srk_saturn_midi_68k_verify_install();",
            "}",
            "",
        )
    )
