#ifndef SRK_SATURN_MIDI_68K_INSTALLER_H
#define SRK_SATURN_MIDI_68K_INSTALLER_H

/* Caller precondition: MC68EC000 is stopped. This API never launches it. */
#define SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS 0x00000000UL
#define SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS 0x00000004UL

int srk_saturn_midi_68k_install_while_stopped(void);
int srk_saturn_midi_68k_verify_install(void);

#endif
