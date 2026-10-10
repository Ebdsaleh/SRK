#ifndef SRK_SATURN_MIDI_68K_SILENT_BATCH_INSTALLER_H
#define SRK_SATURN_MIDI_68K_SILENT_BATCH_INSTALLER_H

/* Caller precondition: MC68EC000 is stopped. This API never launches it. */
int srk_saturn_midi_68k_silent_batch_install_while_stopped(void);
int srk_saturn_midi_68k_silent_batch_verify_install(void);

#endif
