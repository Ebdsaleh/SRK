#include "srk_saturn_midi_mailbox.h"
#include "srk_saturn_midi_generated.h"

#define SRK_MIDI_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)

static void srk_saturn_midi_write_word(unsigned long byte_address, unsigned short value)
{
    SRK_MIDI_SOUND_RAM[byte_address >> 1] = value;
}

static unsigned short srk_saturn_midi_read_word(unsigned long byte_address)
{
    return SRK_MIDI_SOUND_RAM[byte_address >> 1];
}

void srk_saturn_midi_preload_publish(void)
{
    unsigned long index;
    unsigned long base;
    const SRK_SATURN_MIDI_EVENT *event;

    /* Withdraw READY before changing queue/tone state. */
    srk_saturn_midi_write_word(
        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),
        0u
    );

    base = SRK_MIDI_TONE_BANK_ADDRESS;
    for(index=0UL; index<(unsigned long)(SRK_MIDI_TONE_COUNT * SRK_MIDI_TONE_SAMPLES); index++)
        srk_saturn_midi_write_word(
            base + (index * 2UL),
            srk_saturn_midi_tone_bank[index / SRK_MIDI_TONE_SAMPLES][index % SRK_MIDI_TONE_SAMPLES]
        );

    base = SRK_MIDI_QUEUE_ADDRESS;
    for(index=0UL; index<SRK_MIDI_EVENT_COUNT; index++){
        event = &srk_saturn_midi_events[index];
        srk_saturn_midi_write_word(base + (index * 8UL) + 0UL, (unsigned short)(event->time_us >> 16));
        srk_saturn_midi_write_word(base + (index * 8UL) + 2UL, (unsigned short)(event->time_us & 0xFFFFUL));
        srk_saturn_midi_write_word(base + (index * 8UL) + 4UL, (unsigned short)(((unsigned short)event->opcode << 8) | event->channel));
        srk_saturn_midi_write_word(base + (index * 8UL) + 6UL, (unsigned short)(((unsigned short)event->data0 << 8) | event->data1));
    }

    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL), SRK_MIDI_MAILBOX_MAGIC0);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL), SRK_MIDI_MAILBOX_MAGIC1);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL), SRK_MIDI_MAILBOX_VERSION);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL), SRK_MIDI_PRELOAD_WRITE_SEQUENCE);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL), 0u);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL), (unsigned short)SRK_MIDI_EVENT_COUNT);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL), 0u);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL), SRK_MIDI_QUEUE_CAPACITY);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), (unsigned short)SRK_MIDI_EVENT_COUNT);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL), 0u);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_RESERVED * 2UL), 0u);

    /* Publish READY last so the future consumer cannot observe a partial batch. */
    srk_saturn_midi_write_word(
        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),
        SRK_MIDI_MAILBOX_FLAG_READY
    );
}

void srk_saturn_midi_preload_unpublish(void)
{
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL), 0u);
    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), 0u);
}

int srk_saturn_midi_preload_is_ready(void)
{
    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC0)
        return 0;
    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC1)
        return 0;
    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL)) != SRK_MIDI_MAILBOX_VERSION)
        return 0;
    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL)) != SRK_MIDI_QUEUE_CAPACITY)
        return 0;
    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL)) != (unsigned short)SRK_MIDI_EVENT_COUNT)
        return 0;
    return (srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL)) & SRK_MIDI_MAILBOX_FLAG_READY) != 0u;
}
