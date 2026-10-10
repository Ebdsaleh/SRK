#ifndef SRK_SATURN_MIDI_MAILBOX_H
#define SRK_SATURN_MIDI_MAILBOX_H

/* SH-2 producer only. This header does not launch the MC68EC000. */
#define SRK_MIDI_MAILBOX_FLAG_READY 0x0001u
#define SRK_MIDI_MAILBOX_WORD_COUNT 12u
#define SRK_MIDI_PRELOAD_WRITE_SEQUENCE 1u

void srk_saturn_midi_preload_publish(void);
void srk_saturn_midi_preload_unpublish(void);
int srk_saturn_midi_preload_is_ready(void);

#endif
