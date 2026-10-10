#include "srk_saturn_midi_68k_silent_batch_installer.h"
#include "srk_saturn_midi_68k_installer.h"
#include "srk_saturn_midi_68k_silent_batch_program.h"

#define SRK_MIDI_68K_SILENT_BATCH_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)

static void srk_saturn_midi_68k_silent_batch_write_word(
    unsigned long byte_address,
    unsigned short value
)
{
    SRK_MIDI_68K_SILENT_BATCH_SOUND_RAM[byte_address >> 1] = value;
}

static unsigned short srk_saturn_midi_68k_silent_batch_read_word(
    unsigned long byte_address
)
{
    return SRK_MIDI_68K_SILENT_BATCH_SOUND_RAM[byte_address >> 1];
}

static void srk_saturn_midi_68k_silent_batch_write_long(
    unsigned long byte_address,
    unsigned long value
)
{
    srk_saturn_midi_68k_silent_batch_write_word(
        byte_address,
        (unsigned short)(value >> 16)
    );
    srk_saturn_midi_68k_silent_batch_write_word(
        byte_address + 2UL,
        (unsigned short)(value & 0xFFFFUL)
    );
}

static unsigned long srk_saturn_midi_68k_silent_batch_read_long(
    unsigned long byte_address
)
{
    unsigned long high_word;
    unsigned long low_word;

    high_word = (unsigned long)srk_saturn_midi_68k_silent_batch_read_word(byte_address);
    low_word = (unsigned long)srk_saturn_midi_68k_silent_batch_read_word(byte_address + 2UL);
    return (high_word << 16) | low_word;
}

int srk_saturn_midi_68k_silent_batch_verify_install(void)
{
    unsigned long index;

    if(srk_saturn_midi_68k_silent_batch_read_long(
        SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS
    ) != SRK_MIDI_68K_SILENT_BATCH_STACK_ADDRESS)
        return 0;

    if(srk_saturn_midi_68k_silent_batch_read_long(
        SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS
    ) != SRK_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS)
        return 0;

    for(index=0UL;
        index<(unsigned long)SRK_MIDI_68K_SILENT_BATCH_PROGRAM_WORD_COUNT;
        index++){
        if(srk_saturn_midi_68k_silent_batch_read_word(
            SRK_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS + (index * 2UL)
        ) != srk_saturn_midi_68k_silent_batch_program[index])
            return 0;
    }

    return 1;
}

int srk_saturn_midi_68k_silent_batch_install_while_stopped(void)
{
    unsigned long index;

    /* Program first; publish reset vectors only after the complete image exists. */
    for(index=0UL;
        index<(unsigned long)SRK_MIDI_68K_SILENT_BATCH_PROGRAM_WORD_COUNT;
        index++){
        srk_saturn_midi_68k_silent_batch_write_word(
            SRK_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS + (index * 2UL),
            srk_saturn_midi_68k_silent_batch_program[index]
        );
    }

    srk_saturn_midi_68k_silent_batch_write_long(
        SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,
        SRK_MIDI_68K_SILENT_BATCH_STACK_ADDRESS
    );
    srk_saturn_midi_68k_silent_batch_write_long(
        SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,
        SRK_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS
    );

    return srk_saturn_midi_68k_silent_batch_verify_install();
}
