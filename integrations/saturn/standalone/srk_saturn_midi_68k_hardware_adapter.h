#ifndef SRK_SATURN_MIDI_68K_HARDWARE_ADAPTER_H
#define SRK_SATURN_MIDI_68K_HARDWARE_ADAPTER_H

#include "srk_saturn_midi_68k_runtime.h"
#include "srk_saturn_midi_68k_silent_batch_runtime.h"

/* Adapters exist, but production does not pass either one to a runtime yet. */
const SRK_SATURN_MIDI_68K_RUNTIME_OPS *
srk_saturn_midi_68k_hardware_adapter_ops(void);
const SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS *
srk_saturn_midi_68k_silent_batch_hardware_adapter_ops(void);

#endif
