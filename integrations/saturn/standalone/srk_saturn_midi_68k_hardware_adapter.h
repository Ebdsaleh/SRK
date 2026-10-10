#ifndef SRK_SATURN_MIDI_68K_HARDWARE_ADAPTER_H
#define SRK_SATURN_MIDI_68K_HARDWARE_ADAPTER_H

#include "srk_saturn_midi_68k_runtime.h"

/* Adapter exists, but production does not pass it to the runtime yet. */
const SRK_SATURN_MIDI_68K_RUNTIME_OPS *
srk_saturn_midi_68k_hardware_adapter_ops(void);

#endif
