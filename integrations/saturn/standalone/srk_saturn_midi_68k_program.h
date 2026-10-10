#ifndef SRK_SATURN_MIDI_68K_PROGRAM_H
#define SRK_SATURN_MIDI_68K_PROGRAM_H

/* Protocol-only MC68EC000 program image. Not launched by this file. */
#define SRK_MIDI_68K_PROGRAM_ADDRESS 0x00000600UL
#define SRK_MIDI_68K_STACK_ADDRESS 0x0007FFF0UL
#define SRK_MIDI_68K_PROGRAM_WORD_COUNT 81u
#define SRK_MIDI_68K_PROGRAM_BYTE_SIZE 162u

extern const unsigned short srk_saturn_midi_68k_program[SRK_MIDI_68K_PROGRAM_WORD_COUNT];

#endif
